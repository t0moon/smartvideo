from __future__ import annotations

from typing import Any

from channels.base import BaseChannel
from channels.feishu.client import FeishuClient
from channels.feishu.messages import build_review_card, build_status_card
from channels.feishu.ws_listener import (
    start_listener,
    stop_listener,
    register_chat_event_subscribers,
    send_review_card,
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
        card = build_review_card(review_id, project_id, stage)
        result = await client.send_card(open_id, card)
        print(f"  [Feishu] Review card sent for {project_id} / {stage}")
        return {"status": "sent", "channel": "feishu", "result": result}

    async def close(self) -> None:
        if self._client:
            await self._client.close()
