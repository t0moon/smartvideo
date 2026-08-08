from __future__ import annotations

from typing import Any

from channels.base import BaseChannel
from channels.feishu.client import FeishuClient
from channels.feishu.messages import build_status_card
from channels.feishu.review_content import format_review_content, STAGE_NAMES
from channels.feishu.conversation import get_conversation_router
from review.service import ReviewService
from channels.feishu.ws_listener import (
    start_listener,
    stop_listener,
    register_chat_event_subscribers,
)


class FeishuChannel(BaseChannel):
    name = "feishu"

    def __init__(self, app_id: str = "", app_secret: str = "", reviewer_open_id: str = "") -> None:
        self.app_id = app_id
        self.app_secret = app_secret
        self.reviewer_open_id = reviewer_open_id
        self._client: FeishuClient | None = None

    def _ensure_client(self) -> FeishuClient:
        if self._client is None:
            self._client = FeishuClient(self.app_id, self.app_secret)
        return self._client

    async def send_message(self, user_id: str, message: str) -> dict:
        client = self._ensure_client()
        open_id = user_id or self.reviewer_open_id
        if not open_id:
            print("  [Feishu] No open_id configured, skipping message")
            return {"status": "skipped", "channel": "feishu", "reason": "no_open_id"}
        result = await client.send_text_message(open_id, message)
        return {"status": "sent", "channel": "feishu", "result": result}

    async def send_card(self, user_id: str, title: str, content: str, actions: list[dict] | None = None) -> dict:
        client = self._ensure_client()
        open_id = user_id or self.reviewer_open_id
        if not open_id:
            print("  [Feishu] No open_id configured, skipping card")
            return {"status": "skipped", "channel": "feishu", "reason": "no_open_id"}
        card = {
            "config": {"wide_screen_mode": True},
            "header": {"title": {"tag": "plain_text", "content": title}, "template": "blue"},
            "elements": [
                {"tag": "markdown", "content": content},
            ],
        }
        if actions:
            card["elements"].append({"tag": "hr"})
            card["elements"].append({"tag": "action", "actions": actions})
        result = await client.send_card(open_id, card)
        return {"status": "sent", "channel": "feishu", "result": result}

    async def notify_review(self, project_id: str, review_id: str, stage: str) -> dict:
        client = self._ensure_client()
        open_id = self.reviewer_open_id
        if not open_id:
            print("  [Feishu] No reviewer_open_id configured, skipping review notification")
            return {"status": "skipped", "channel": "feishu", "reason": "no_open_id"}

        # ── card-less: push model output + register with ConversationRouter ──
        stage_name = STAGE_NAMES.get(stage, stage)
        try:
            svc = ReviewService()
            review = svc.get_review(review_id)
            if review and review.content:
                content_text = format_review_content(stage, review.content)
                if content_text:
                    header = f"\U0001f4cc {stage_name}\u7ed3\u679c\u5982\u4e0b\uff1a"
                    prompt = f"{header}\n{content_text}\n\n\u8bf7\u56de\u590d\u300c\u6279\u51c6\u300d\u7ee7\u7eed\uff0c\u6216\u300c\u9a73\u56de + \u4fee\u6539\u610f\u89c1\u300d\u6765\u8c03\u6574\u540e\u91cd\u65b0\u751f\u6210\u3002"
                    await client.send_text_message(open_id, prompt)
        except Exception as exc:
            print(f"  [Feishu] Failed to send review content for {review_id}: {exc}")

        # Register with ConversationRouter so the user's next text reply
        # is routed to the correct review (no card callback needed).
        router = get_conversation_router()
        router.register(open_id, review_id, project_id, stage, stage_name)
        print(f"  [Feishu] Review prompt sent for {project_id} / {stage}")
        return {"status": "sent", "channel": "feishu", "result": {}}

    async def close(self) -> None:
        if self._client:
            await self._client.close()
