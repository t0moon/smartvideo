"""Feishu WebSocket long-connection listener (official lark-oapi SDK).

The app connects *outward* to Feishu's WebSocket endpoint and receives events /
card-action callbacks over a persistent connection. Uses the official
``lark-oapi`` SDK which handles the handshake, token refresh, ping-pong and
reconnect internally (the only supported way for Feishu long-connection mode).
Supports IM chat: users can send messages to the bot to create video projects.
"""
from __future__ import annotations

import json
import time
import threading
from typing import Any

# NOTE: ``lark_oapi`` (heavy SDK) and ``runtime.workflow`` are imported lazily
# inside the functions that actually need them. Importing them at module level
# would pull the entire Feishu WS SDK + the workflow/runtime chain during
# ``app.main`` import, deadlocking on a partially-initialised import loop.

from app.config import FEISHU_APP_ID, FEISHU_APP_SECRET, FEISHU_REVIEWER_OPEN_ID
from channels.feishu.async_executor import run_async as _run_async
from channels.feishu.client import FeishuClient
from channels.feishu.messages import build_review_card
from channels.feishu.review_content import format_review_content, STAGE_NAMES
from project.service import ProjectService
from review.service import ReviewService
from events.bus import (
    Event, get_event_bus,
    EVENT_PIPELINE_STARTED, EVENT_PIPELINE_COMPLETED,
    EVENT_PIPELINE_PAUSED, EVENT_PIPELINE_ERROR,
)

_svc = ReviewService()
_proj = ProjectService()
# Track {project_id: (sender_open_id, message_id)} for sending status updates
_user_chat_map: dict[str, tuple[str, str]] = {}
_ws_client = None
_ws_thread: threading.Thread | None = None
_chat_client: FeishuClient | None = None

# ── message / brief dedup (idempotency) ────────────────────────────────────
# Feishu may retry or re-deliver events on network blips / WS reconnect.
# Users may also accidentally send the same brief twice. Both are caught here.

_SEEN_TTL = 600                 # forget message IDs after 10 min
_BRIEF_DUP_WINDOW = 5           # block identical briefs within 5 s
_seen_message_ids: dict[str, float] = {}    # {message_id: expire_timestamp}
_recent_briefs: dict[str, float] = {}       # {f'{sender}:{brief}': expire_ts}


def _is_duplicate_message(message_id: str) -> bool:
    """Return True if *message_id* was already processed in this session."""
    now = time.time()
    stale = [k for k, v in _seen_message_ids.items() if v < now]
    for k in stale:
        _seen_message_ids.pop(k, None)
    if message_id in _seen_message_ids:
        return True
    _seen_message_ids[message_id] = now + _SEEN_TTL
    return False


def _is_duplicate_brief(sender: str, brief: str) -> bool:
    """Return True if *sender* posted the same *brief* in the last few seconds."""
    now = time.time()
    key = f'{sender}:{brief.strip()}'
    stale = [k for k, v in _recent_briefs.items() if v < now]
    for k in stale:
        _recent_briefs.pop(k, None)
    if key in _recent_briefs:
        return True
    _recent_briefs[key] = now + _BRIEF_DUP_WINDOW
    return False


def _get_chat_client() -> FeishuClient:
    """Return a FeishuClient instance bound to the shared async executor loop."""
    global _chat_client
    if _chat_client is None:
        # The httpx.AsyncClient must be created on the same loop that will run it.
        _chat_client = _run_async(_create_client())
    return _chat_client


async def _create_client() -> FeishuClient:
    return FeishuClient()


# ── card action handling ──────────────────────────────────────────────────

def _coerce_card_value(raw: Any) -> dict:
    """Feishu may deliver ``action.value`` as a JSON *string* or a *dict*
    depending on the card schema version; normalize both to a dict."""
    if raw is None:
        return {}
    if isinstance(raw, dict):
        return raw
    if isinstance(raw, str):
        try:
            parsed = json.loads(raw)
            return parsed if isinstance(parsed, dict) else {}
        except json.JSONDecodeError:
            return {}
    return {}


def _handle_card_action(header: dict, action: dict) -> dict:
    """Process a card action trigger (approve / reject / view)."""
    from runtime.workflow import WorkflowRuntime
    # Normalize the action value (may arrive as dict or JSON string).
    raw_value = action.get("value")
    # Defensive: tolerate a double-wrapped payload (legacy shape).
    if raw_value is None and isinstance(action.get("action"), dict):
        raw_value = action["action"].get("value")
    value = _coerce_card_value(raw_value)
    action_name = value.get("action", "")
    review_id = value.get("review_id", "")
    project_id = value.get("project_id", "")

    if action_name in ("approve", "reject") and review_id:
        review = _svc.get_review(review_id)
        if review is None:
            return {"status": "error", "message": "Review not found"}

        pid = review.project_id
        if action_name == "approve":
            _svc.approve(review_id, reviewer="feishu")
            print(f"  [Feishu-WS] Approved review {review_id} for project {pid}")
        else:
            _svc.reject(review_id, reviewer="feishu")
            print(f"  [Feishu-WS] Rejected review {review_id} for project {pid}")

        # Resume pipeline in a background thread — the card callback must
        # ack within 3s, while resume may run video generation for minutes.
        def _resume_bg() -> None:
            try:
                WorkflowRuntime().resume(pid, review_id)
            except Exception as exc:
                print(f"  [Feishu-WS] Resume error for {pid}: {exc}")
                try:
                    WorkflowRuntime().record_resume_error(pid, exc)
                except Exception:
                    pass

        threading.Thread(target=_resume_bg, daemon=True).start()
        return {"status": "ok", "action": action_name, "project_id": pid}

    if action_name == "view":
        return {"status": "ok", "action": "view"}

    return {"status": "received", "action": action_name}


def _on_card_action(data: P2CardActionTrigger) -> P2CardActionTriggerResponse:
    """SDK callback for card.action.trigger — must return an ack response."""
    from lark_oapi.event.callback.model.p2_card_action_trigger import (
        P2CardActionTriggerResponse,
        CallBackToast,
    )
    action_value = data.event.action.value if (data.event and data.event.action) else {}
    header = {"event_type": "card.action.trigger"}
    # Pass the action value at the top level so _handle_card_action can read
    # action.get("value") correctly (matches the dict shape it expects).
    action = {"value": action_value}
    # Diagnostic log — confirms whether Feishu is actually pushing the
    # card.action.trigger event to this backend (后台是否已订阅该事件).
    print(f"  [Feishu-WS] >>> card.action.trigger received: {action_value}")
    _handle_card_action(header, action)
    resp = P2CardActionTriggerResponse()
    resp.toast = CallBackToast()
    resp.toast.type = "info"
    resp.toast.content = "已处理"
    return resp


# ── IM message (chat) handling ────────────────────────────────────────────

def _find_pending_review_for_sender(sender: str):
    """Return the most recent pending review created from a chat with *sender*."""
    pending = _svc.list_pending()
    # Prefer reviews whose project was created by this sender.
    for review in reversed(pending):
        pid = review.project_id
        if pid in _user_chat_map and _user_chat_map[pid][0] == sender:
            return review
    return None


def _handle_text_approval(sender: str, message_id: str, text: str, approve: bool) -> bool:
    """If the user is replying 'approve'/'reject' without a card, resolve the latest pending review."""
    from runtime.workflow import WorkflowRuntime
    review = _find_pending_review_for_sender(sender)
    if review is None:
        return False

    action_name = "approve" if approve else "reject"
    review_id = review.review_id
    pid = review.project_id
    print(f"  [Feishu-Chat] Text {action_name} for review {review_id} / project {pid}")

    try:
        if approve:
            _svc.approve(review_id, reviewer="feishu")
        else:
            _svc.reject(review_id, reviewer="feishu")
    except Exception as exc:
        print(f"  [Feishu-Chat] Failed to {action_name} review {review_id}: {exc}")
        return False

    def _resume_bg() -> None:
        try:
            WorkflowRuntime().resume(pid, review_id)
        except Exception as exc:
            print(f"  [Feishu-Chat] Resume error for {pid}: {exc}")
            try:
                WorkflowRuntime().record_resume_error(pid, exc)
            except Exception:
                pass

    threading.Thread(target=_resume_bg, daemon=True).start()

    try:
        _run_async(_get_chat_client().reply_to_message(
            message_id, f"已{'批准' if approve else '驳回'}，继续执行下一步..."
        ))
    except Exception as exc:
        print(f"  [Feishu-Chat] Approval ack reply failed: {exc}")
    return True


def _handle_im_message(event: dict) -> None:
    """Process an incoming IM message and kick off a video project.

    Idempotency guarantees:
    - message_id TTL cache — same event re-delivered by Feishu is skipped.
    - brief dedup window — same sender+text within 5s returns a hint instead
      of creating a duplicate project.
    - project is created BEFORE the user-facing ack, so the reply already
      carries the project_id.
    """
    message = event.get("message", {})
    sender = event.get("sender", {}).get("sender_id", {}).get("open_id", "")
    message_id = message.get("message_id", "")
    msg_type = message.get("msg_type", "")
    content_raw = message.get("content", "{}")

    if not sender or not message_id or msg_type != "text":
        return

    # Parse message text
    try:
        content = json.loads(content_raw)
        text = content.get("text", "").strip()
    except (json.JSONDecodeError, KeyError):
        text = content_raw.strip()

    if not text:
        return

    # ── Idempotency gate 1: duplicate message_id (Feishu retry / WS replay) ─
    if _is_duplicate_message(message_id):
        print(f"  [Feishu-Chat] Duplicate message_id {message_id} — skipped")
        return

    print(f"  [Feishu-Chat] Received from {sender}: {text[:80]}")

    client = _get_chat_client()

    # ── Special command: reveal the user's open_id ───────────────────────
    if text.strip() in ("我的ID", "我的id", "id", "ID", "open_id"):
        try:
            _run_async(client.reply_to_message(
                message_id,
                f"您的飞书 Open ID 是:\n`{sender}`\n\n把这个值填到 `.env` 文件的 `FEISHU_REVIEWER_OPEN_ID=` 后面即可收到审批卡片通知。"
            ))
        except Exception as e:
            print(f"  [Feishu-Chat] Failed to reply (check im:message permission): {e}")
        return

    # ── Text-based approval / rejection fallback ─────────────────────────
    approve_words = {"批准", "同意", "通过", "approve", "ok", "好的", "yes", "y"}
    reject_words = {"驳回", "拒绝", "不通过", "reject", "no", "否", "重新做"}
    lower = text.strip().lower()
    if lower in approve_words or lower in reject_words:
        if _handle_text_approval(sender, message_id, text, approve=(lower in approve_words)):
            return
        try:
            _run_async(client.reply_to_message(message_id, "当前没有待审批的项目，无法处理该指令。"))
        except Exception as exc:
            print(f"  [Feishu-Chat] No-pending-review reply failed: {exc}")
        return

    # ── Idempotency gate 2: duplicate brief within the dedup window ──────
    if _is_duplicate_brief(sender, text):
        try:
            _run_async(client.reply_to_message(
                message_id,
                "您刚发送了相同需求，正在处理中，请稍候查看审批通知...\n如需重新提交，请稍等几秒后再试。"
            ))
        except Exception as exc:
            print(f"  [Feishu-Chat] Dup-brief reply failed: {exc}")
        return

    # ── Create project FIRST (so the ack reply carries the project_id) ───
    pid = ""
    try:
        project_name = text[:50] + ("..." if len(text) > 50 else "")
        project = _proj.create_project(name=project_name, brief=text)
        pid = project.project_id

        _user_chat_map[pid] = (sender, message_id)
        _proj.update_project(pid, {
            "meta": {
                **project.meta,
                "feishu_from_user": sender,
                "feishu_message_id": message_id,
            }
        })
        print(f"  [Feishu-Chat] Created project {pid} for {sender}")
    except Exception as exc:
        print(f"  [Feishu-Chat] Failed to create project: {exc}")
        try:
            _run_async(client.reply_to_message(message_id, f"创建项目失败：{exc}"))
        except Exception:
            pass
        return

    # ── Reply with project_id (user sees which project was created) ──────
    try:
        _run_async(client.reply_to_message(
            message_id,
            f"收到您的需求！正在创建视频项目，请稍候...\n项目 ID: `{pid}`\n📝 正在理解需求"
        ))
    except Exception as e:
        print(f"  [Feishu-Chat] Ack reply failed (check im:message permission): {e}")

    # ── Run pipeline in background (must return within 3s) ───────────────
    t = threading.Thread(target=_run_pipeline_and_notify, args=(pid, text, message_id), daemon=True)
    t.start()


def _run_pipeline_and_notify(pid: str, text: str, message_id: str) -> None:
    """Run the workflow pipeline and notify the user on completion / error."""
    from runtime.workflow import WorkflowRuntime
    try:
        runtime = WorkflowRuntime()
        result = runtime.run_pipeline(pid, text)

        if result and not result.startswith("__PAUSED__"):
            try:
                _run_async(_get_chat_client().reply_to_message(
                    message_id,
                    f"✅ 视频已生成完毕！项目 ID: {pid}\n请查看项目详情获取下载链接。"
                ))
            except Exception:
                pass
            _user_chat_map.pop(pid, None)
        # If paused, the pipeline-paused subscriber sends the review card.
    except Exception as exc:
        print(f"  [Feishu-Chat] Pipeline error for {pid}: {exc}")
        try:
            _run_async(_get_chat_client().reply_to_message(message_id, f"❌ 视频生成失败：{exc}"))
        except Exception:
            pass
        _user_chat_map.pop(pid, None)


def _on_im_message_read(data: P2ImMessageMessageReadV1) -> None:
    """Ack 'message read' receipt events — no business action needed."""
    return


def _on_im_message(data: P2ImMessageReceiveV1) -> None:
    """SDK callback for im.message.receive_v1 — build a dict and dispatch."""
    msg = data.event.message
    sender_open_id = ""
    if data.event.sender and data.event.sender.sender_id:
        sender_open_id = data.event.sender.sender_id.open_id or ""
    event = {
        "message": {
            "message_id": msg.message_id,
            "chat_id": msg.chat_id,
            "content": msg.content,
            "msg_type": msg.message_type,
        },
        "sender": {"sender_id": {"open_id": sender_open_id}},
    }
    _handle_im_message(event)


# ── review card sending ──────────────────────────────────────────────────

def send_review_card(project_id: str, stage: str, review_id: str,
                     project_name: str = "", review_content: str = "") -> None:
    """Send the interactive approval card to the chat initiator (if any).

    Before the action card, pushes the model's output content as a text
    message so the user can read what was generated and make an informed
    decision (approve / reject).
    """
    if project_id not in _user_chat_map:
        print(f"  [Feishu-Card] No chat mapping for {project_id}, skip card")
        return
    sender, _ = _user_chat_map[project_id]

    # ── 推送模型产出内容（在审批卡片之前） ──
    stage_name = STAGE_NAMES.get(stage, stage)
    try:
        review = _svc.get_review(review_id)
        if review and review.content:
            content_text = format_review_content(stage, review.content)
            if content_text:
                header = f"\U0001f4cc {stage_name}\u7ed3\u679c\u5982\u4e0b\uff1a"
                _run_async(_get_chat_client().send_text_message(sender, header + "\n" + content_text))
    except Exception as exc:
        print(f"  [Feishu-Card] Failed to send review content for {review_id}: {exc}")

    card = build_review_card(review_id, project_id, stage, project_name, review_content)
    try:
        _run_async(_get_chat_client().send_card(sender, card))
        print(f"  [Feishu-Card] Sent review card for {project_id} ({stage}) to {sender}")
    except Exception as e:
        print(f"  [Feishu-Card] Failed to send card: {e}")


# ── pipeline status subscribers ──────────────────────────────────────────

def _on_pipeline_paused(event: Event) -> None:
    """Forward pipeline pause events as a Feishu approval card.

    The interactive card is delivered by ChannelManager via
    ``FeishuChannel.notify_review`` to FEISHU_REVIEWER_OPEN_ID. When the chat
    initiator is *not* that reviewer (or no reviewer is configured), we also
    push the actionable card directly into the conversation so the person who
    started the project can approve it right there.
    """
    pid = event.data.get("project_id", "")
    if pid not in _user_chat_map:
        return
    sender, _ = _user_chat_map[pid]
    stage = event.data.get("stage", "?")
    review_id = event.data.get("review_id", "")

    stage_names = {
        "requirement": "需求理解",
        "storyboard": "分镜脚本",
        "asset_prep":  "资产确认",
        "video_review": "视频审核",
        "video_gen": "视频生成",
    }
    stage_cn = stage_names.get(stage, stage)

    # Same person / no card → ChannelManager.notify_review already sent the card
    # to the reviewer; a plain text hint is enough (avoid a duplicate card).
    if not review_id or sender == FEISHU_REVIEWER_OPEN_ID:
        try:
            _run_async(_get_chat_client().send_text_message(
                sender,
                f"⏸️ {stage_cn}阶段已完成，待审批中..."
            ))
        except Exception as exc:
            print(f"  [Feishu-Chat] Status update error: {exc}")
        return

    # Different chat initiator → deliver the actionable card into their chat.
    send_review_card(pid, stage, review_id, project_name=pid)


def _on_pipeline_completed(event: Event) -> None:
    """Notify the user when their pipeline finishes."""
    pid = event.data.get("project_id", "")
    if pid not in _user_chat_map:
        return
    sender, _ = _user_chat_map[pid]
    try:
        _run_async(_get_chat_client().send_text_message(
            sender, f"✅ 视频项目已完成！项目 ID: {pid}\n请在 Web 端查看和下载成片。"))
    except Exception as exc:
        print(f"  [Feishu-Chat] Completion notice error: {exc}")
    _user_chat_map.pop(pid, None)


def _on_pipeline_error(event: Event) -> None:
    """Notify the user when their pipeline fails."""
    pid = event.data.get("project_id", "")
    if pid not in _user_chat_map:
        return
    sender, _ = _user_chat_map[pid]
    error = event.data.get("error", "未知错误")
    try:
        _run_async(_get_chat_client().send_text_message(sender, f"❌ 视频生成失败: {error}"))
    except Exception as exc:
        print(f"  [Feishu-Chat] Error notice error: {exc}")
    _user_chat_map.pop(pid, None)


def register_chat_event_subscribers() -> None:
    """Register event bus subscribers for Feishu chat status updates."""
    bus = get_event_bus()
    bus.subscribe(EVENT_PIPELINE_PAUSED, _on_pipeline_paused)
    bus.subscribe(EVENT_PIPELINE_COMPLETED, _on_pipeline_completed)
    bus.subscribe(EVENT_PIPELINE_ERROR, _on_pipeline_error)
    print("  [Feishu-Chat] Pipeline event subscribers registered")


# ── SDK client lifecycle ─────────────────────────────────────────────────

def _build_event_handler():
    import lark_oapi as lark
    return (
        lark.EventDispatcherHandler.builder("", "")
        .register_p2_im_message_receive_v1(_on_im_message)
        .register_p2_im_message_message_read_v1(_on_im_message_read)
        .register_p2_card_action_trigger(_on_card_action)
        .build()
    )


def _run_ws_client() -> None:
    """Blocking entrypoint for the WS client (runs in a background thread)."""
    import lark_oapi as lark
    global _ws_client
    _ws_client = lark.ws.Client(
        FEISHU_APP_ID, FEISHU_APP_SECRET,
        event_handler=_build_event_handler(),
        log_level=lark.LogLevel.INFO,
    )
    _ws_client.start()


async def start_listener() -> None:
    """Start the Feishu WS long-connection listener in a background thread."""
    global _ws_thread
    register_chat_event_subscribers()
    _ws_thread = threading.Thread(target=_run_ws_client, daemon=True)
    _ws_thread.start()
    print("  [Feishu-WS] Listener started (background thread)")


async def stop_listener() -> None:
    """Stop the Feishu WS listener.

    The official lark-oapi SDK has no public stop() API; the client runs in a
    daemon thread that is reaped on process exit. We clear references here so
    a subsequent start_listener() rebuilds a fresh client.
    """
    global _ws_client, _ws_thread
    _ws_client = None
    _ws_thread = None
    print("  [Feishu-WS] Listener stopped")
