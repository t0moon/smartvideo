"""Feishu Open API client (async)."""
from __future__ import annotations

import json
import time
from typing import Any

import httpx

from app.config import FEISHU_APP_ID, FEISHU_APP_SECRET

BASE_URL = "https://open.feishu.cn/open-apis"


class FeishuClient:
    def __init__(self, app_id: str = "", app_secret: str = "") -> None:
        self.app_id = app_id or FEISHU_APP_ID
        self.app_secret = app_secret or FEISHU_APP_SECRET
        self._token: str = ""
        self._token_expires_at: float = 0
        self._client = httpx.AsyncClient(timeout=30)

    async def _get_tenant_token(self) -> str:
        if self._token and time.time() < self._token_expires_at:
            return self._token

        resp = await self._client.post(f"{BASE_URL}/auth/v3/tenant_access_token/internal", json={
            "app_id": self.app_id,
            "app_secret": self.app_secret,
        })
        data = resp.json()
        self._token = data.get("tenant_access_token", "")
        expire = data.get("expire", 7200)
        self._token_expires_at = time.time() + expire - 60
        return self._token

    async def send_text_message(self, open_id: str, text: str) -> dict[str, Any]:
        token = await self._get_tenant_token()
        resp = await self._client.post(
            f"{BASE_URL}/im/v1/messages?receive_id_type=open_id",
            headers={"Authorization": f"Bearer {token}"},
            json={
                "receive_id": open_id,
                "msg_type": "text",
                "content": json.dumps({"text": text}),
            },
        )
        return resp.json()

    async def reply_to_message(self, message_id: str, text: str) -> dict[str, Any]:
        """Reply to a specific message in the same conversation thread."""
        token = await self._get_tenant_token()
        resp = await self._client.post(
            f"{BASE_URL}/im/v1/messages/{message_id}/reply",
            headers={"Authorization": f"Bearer {token}"},
            json={
                "content": json.dumps({"text": text}),
                "msg_type": "text",
            },
        )
        if resp.status_code >= 400:
            raise RuntimeError(f"Feishu reply API error {resp.status_code}: {resp.text[:300]}")
        return resp.json()

    async def send_card(self, open_id: str, card_json: dict[str, Any]) -> dict[str, Any]:
        token = await self._get_tenant_token()
        content = json.dumps(card_json, ensure_ascii=False)
        resp = await self._client.post(
            f"{BASE_URL}/im/v1/messages?receive_id_type=open_id",
            headers={"Authorization": f"Bearer {token}"},
            json={
                "receive_id": open_id,
                "msg_type": "interactive",
                "content": content,
            },
        )
        return resp.json()

    async def reply_with_card(self, message_id: str, card_json: dict[str, Any]) -> dict[str, Any]:
        """Reply to a specific message with an interactive card."""
        token = await self._get_tenant_token()
        content = json.dumps(card_json, ensure_ascii=False)
        resp = await self._client.post(
            f"{BASE_URL}/im/v1/messages/{message_id}/reply",
            headers={"Authorization": f"Bearer {token}"},
            json={
                "content": content,
                "msg_type": "interactive",
            },
        )
        return resp.json()

    async def close(self) -> None:
        await self._client.aclose()
