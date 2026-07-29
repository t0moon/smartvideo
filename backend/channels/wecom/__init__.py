from __future__ import annotations

from typing import Any

from channels.base import BaseChannel


class WeComChannel(BaseChannel):
    name = 'wecom'

    def __init__(self, webhook_url: str = '') -> None:
        self.webhook_url = webhook_url

    async def send_message(self, user_id: str, message: str) -> dict:
        print(f'  [WeCom] To {user_id}: {message[:80]}...')
        return {'status': 'queued', 'channel': 'wecom'}

    async def send_card(self, user_id: str, title: str, content: str, actions: list[dict] | None = None) -> dict:
        print(f'  [WeCom] Card to {user_id}: {title}')
        return {'status': 'queued', 'channel': 'wecom'}

    async def notify_review(self, project_id: str, review_id: str, stage: str) -> dict:
        print(f'  [WeCom] Review notification: {project_id} / {stage}')
        return {'status': 'queued', 'channel': 'wecom'}
