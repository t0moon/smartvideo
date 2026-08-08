"""Per-user conversation state machine for card-less review flow.

Replaces the old ``_user_chat_map`` + ``build_review_card`` approach with a
proper state machine that tracks which review a user is expected to respond
to, handles timeouts / re-prompts, and queues multiple pending reviews so the
same user can drive several projects without ambiguity.
"""
from __future__ import annotations

import time
import threading
from dataclasses import dataclass, field
from typing import Any


@dataclass
class PendingReview:
    review_id: str
    project_id: str
    stage: str           # requirement / storyboard / asset_prep / video_review
    stage_name: str      # human-readable (e.g. "需求分析")
    sender: str          # Feishu open_id
    bot_message_id: str  # last bot text for reply-threading
    created_at: float = field(default_factory=time.time)
    timeout_at: float = 0
    retry_count: int = 0


class ConversationRouter:
    """Per-user state machine for card-less review conversations.

    Lifecycle
    ---------
    1. ``register()`` — called when a pipeline pauses at a HITL node.
    2. ``route()`` — called on every incoming text message from a user whose
       state is "reviewing".
    3. ``release()`` — called when the review is resolved (approved/rejected).
    4. ``check_timeouts()`` — periodic; any review past timeout_at gets a
       re-prompt or is expired.
    """

    # 30 min before first re-prompt, 60 min before giving up.
    TIMEOUT_WARN_S = 30 * 60
    MAX_RETRIES = 3

    def __init__(self) -> None:
        self._states: dict[str, PendingReview] = {}     # user_id → current review
        self._queues: dict[str, list[PendingReview]] = {}  # user_id → backlog

    @property
    def bot(self):
        """Lazy import to avoid pulling FeishuClient at module load."""
        from channels.feishu.client import FeishuClient
        return FeishuClient()

    # ── public API ────────────────────────────────────────────────────────

    def register(self, user_id: str, review_id: str, project_id: str,
                 stage: str, stage_name: str, bot_message_id: str = "") -> None:
        """Register the review the user should respond to next."""
        pr = PendingReview(
            review_id=review_id, project_id=project_id,
            stage=stage, stage_name=stage_name,
            sender=user_id, bot_message_id=bot_message_id,
            timeout_at=time.time() + self.TIMEOUT_WARN_S,
        )
        if user_id in self._states:
            self._queues.setdefault(user_id, []).append(pr)
            print(f"  [Conv] user {user_id[:12]} has active review; queued {review_id[:12]}")
            return
        self._states[user_id] = pr
        print(f"  [Conv] registered review {review_id[:12]} for user {user_id[:12]}")

    def route(self, user_id: str, message_id: str, text: str) -> str:
        """Route an incoming text to the right handler.

        Returns one of: 'new_project' (text should create a project),
        'handled' (intent processed and review resolved/modified),
        or 'clarify' / 'remind' (needs re-prompt).
        """
        if user_id not in self._states:
            return "new_project"

        pr = self._states[user_id]
        from channels.feishu.intent import parse_intent
        intent, feedback_text = parse_intent(text)

        if intent == "approve":
            return self._do_approve(pr, message_id)

        if intent in ("reject", "reject_feedback"):
            return self._do_reject(pr, message_id, feedback_text)

        if intent == "clarify":
            self._reprompt(pr, message_id)
            return "clarify"

        # unrelated / unknown → gentle reminder
        self._remind(pr, message_id)
        return "remind"

    def release(self, user_id: str) -> None:
        """Remove the resolved review and promote the next queued one (if any)."""
        self._states.pop(user_id, None)
        queue = self._queues.get(user_id, [])
        if queue:
            next_pr = queue.pop(0)
            self._states[user_id] = next_pr
            print(f"  [Conv] promoted queued review {next_pr.review_id[:12]} for {user_id[:12]}")
            from channels.feishu.async_executor import run_async
            # Re-send the prompt for the promoted review
            run_async(self._send_content(next_pr))
        if not queue:
            self._queues.pop(user_id, None)

    def release_if(self, project_id: str) -> None:
        """Release whatever review is bound to *project_id* (best-effort)."""
        for uid, pr in list(self._states.items()):
            if pr.project_id == project_id:
                self.release(uid)
                return

    # ── internal ─────────────────────────────────────────────────────────

    def _do_approve(self, pr: PendingReview, _message_id: str) -> str:
        from review.service import ReviewService
        from runtime.workflow import WorkflowRuntime
        svc = ReviewService()
        svc.approve(pr.review_id, reviewer="feishu")
        print(f"  [Conv] approved {pr.review_id[:12]} ({pr.stage_name})")
        from channels.feishu.async_executor import run_async
        try:
            run_async(self.bot.reply_to_message(
                pr.bot_message_id,
                f"已批准 {pr.stage_name}，继续执行..."
            ))
        except Exception:
            pass
        self.release(pr.sender)

        def _resume() -> None:
            try:
                WorkflowRuntime().resume(pr.project_id, pr.review_id)
            except Exception as exc:
                print(f"  [Conv] resume error for {pr.project_id}: {exc}")
                try:
                    WorkflowRuntime().record_resume_error(pr.project_id, exc)
                except Exception:
                    pass
        threading.Thread(target=_resume, daemon=True).start()
        return "handled"

    def _do_reject(self, pr: PendingReview, message_id: str, feedback: str) -> str:
        from review.service import ReviewService
        from runtime.workflow import WorkflowRuntime
        svc = ReviewService()
        if feedback:
            svc.add_comment(pr.review_id, feedback, "feishu")
            svc.partial_revision(pr.review_id, "feishu", feedback)
            result = svc.get_review(pr.review_id)
            print(f"  [Conv] partial_revision {pr.review_id[:12]} ({pr.stage_name}) feedback={feedback[:40]}")
        else:
            svc.reject(pr.review_id, reviewer="feishu")
            print(f"  [Conv] rejected {pr.review_id[:12]} ({pr.stage_name})")

        from channels.feishu.async_executor import run_async
        try:
            ack = f"已驳回 {pr.stage_name}，将根据意见重新生成..." if feedback else f"已驳回 {pr.stage_name}，流程终止。"
            run_async(self.bot.reply_to_message(message_id, ack))
        except Exception:
            pass

        if not feedback:
            self.release(pr.sender)
            return "handled"

        # partial_revision: resume with feedback
        def _resume() -> None:
            try:
                result = WorkflowRuntime().resume(pr.project_id, pr.review_id)
            except Exception as exc:
                print(f"  [Conv] resume error for {pr.project_id}: {exc}")
                try:
                    WorkflowRuntime().record_resume_error(pr.project_id, exc)
                except Exception:
                    pass
                return

            # After LLM regenerates with feedback, deliver the revised content
            # directly to the user in the conversation thread.
            try:
                from review.service import ReviewService
                from channels.feishu.review_content import format_review_content
                svc = ReviewService()
                reviews = svc.list_by_project(pr.project_id)
                new_review = next(
                    (r for r in reversed(reviews)
                     if r.stage.value == "storyboard" and r.status.value == "pending"),
                    None,
                )
                if new_review and new_review.content:
                    body = format_review_content("storyboard", new_review.content)
                    header = f"已根据反馈重新生成{pr.stage_name}，结果如下："
                    run_async(self.bot.reply_to_message(message_id, f"{header}\n{body}"))
                    self.register(pr.sender, new_review.review_id, pr.project_id,
                                  "storyboard", pr.stage_name, pr.bot_message_id)
            except Exception as exc:
                print(f"  [Conv] failed to deliver revised content: {exc}")
        threading.Thread(target=_resume, daemon=True).start()
        return "handled"

    def _reprompt(self, pr: PendingReview, message_id: str) -> None:
        from channels.feishu.async_executor import run_async
        try:
            run_async(self.bot.reply_to_message(
                message_id,
                f"\u5f53\u524d\u5f85\u5ba1\u6279\uff1a{pr.stage_name}\n\u8bf7\u56de\u590d\u300c\u6279\u51c6\u300d\u7ee7\u7eed\uff0c\u6216\u300c\u9a73\u56de + \u4fee\u6539\u610f\u89c1\u300d\u6765\u8c03\u6574\u540e\u91cd\u65b0\u751f\u6210\u3002"
            ))
        except Exception:
            pass

    async def _send_content(self, pr: PendingReview) -> None:
        """Re-send the review content text (used when promoting queued reviews)."""
        from review.service import ReviewService
        from channels.feishu.review_content import format_review_content
        svc = ReviewService()
        review = svc.get_review(pr.review_id)
        if review and review.content:
            text = format_review_content(pr.stage, review.content)
            if text:
                await self.bot.send_text_message(pr.sender,
                    f"[待审批] {pr.stage_name}:\n{text}")

    def _remind(self, pr: PendingReview, message_id: str) -> None:
        """Gentle reminder that a review is pending."""
        from channels.feishu.async_executor import run_async
        try:
            run_async(self.bot.reply_to_message(
                message_id,
                f"\u5f53\u524d\u6709\u4e00\u4e2a\u5f85\u5ba1\u6279\u7684 {pr.stage_name}\uff0c\u8bf7\u5148\u56de\u590d\u300c\u6279\u51c6\u300d\u6216\u300c\u9a73\u56de\u300d\u6765\u51b3\u5b9a\u662f\u5426\u7ee7\u7eed\u3002\n"
                f"如需创建新项目，请先处理完当前审批。"
            ))
        except Exception:
            pass

    def check_timeouts(self) -> None:
        """Scan for timed-out reviews and re-prompt or expire them."""
        now = time.time()
        for uid, pr in list(self._states.items()):
            if pr.timeout_at and now > pr.timeout_at:
                pr.retry_count += 1
                if pr.retry_count > self.MAX_RETRIES:
                    print(f"  [Conv] review {pr.review_id[:12]} expired after {self.MAX_RETRIES} retries")
                    self.release(uid)
                    from channels.feishu.async_executor import run_async
                    try:
                        run_async(self.bot.send_text_message(
                            uid, f"审批 {pr.stage_name} 已超时，请重新发起。"
                        ))
                    except Exception:
                        pass
                    continue
                pr.timeout_at = now + (self.TIMEOUT_WARN_S * (pr.retry_count + 1))
                from channels.feishu.async_executor import run_async
                try:
                    run_async(self.bot.send_text_message(
                        uid,
                        f"[\u63d0\u9192 {pr.retry_count}/{self.MAX_RETRIES}] \u8fd8\u6709\u4e00\u4e2a\u5f85\u5ba1\u6279\u7684 {pr.stage_name}\uff0c"
                        f"\u8bf7\u56de\u590d\u300c\u6279\u51c6\u300d\u7ee7\u7eed\u6216\u300c\u9a73\u56de\u300d\u91cd\u65b0\u751f\u6210\u3002"
                    ))
                except Exception:
                    pass
                print(f"  [Conv] re-prompted {pr.review_id[:12]} for {uid[:12]} (retry {pr.retry_count})")


# Global singleton
_router: ConversationRouter | None = None


def get_conversation_router() -> ConversationRouter:
    global _router
    if _router is None:
        _router = ConversationRouter()
    return _router
