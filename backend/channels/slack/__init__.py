from __future__ import annotations

from typing import Any

from channels.base import BaseChannel


class SlackChannel(BaseChannel):
    name = 'slack'

    def __init__(self, webhook_url: str = '') -> None:
        self.webhook_url = webhook_url

    async def send_message(self, user_id: str, message: str) -> dict:
        print(f'  [Slack] To {user_id}: {message[:80]}...')
        return {'status': 'queued', 'channel': 'slack'}

    async def send_card(self, user_id: str, title: str, content: str, actions: list[dict] | None = None) -> dict:
        print(f'  [Slack] Card to {user_id}: {title}')
        return {'status': 'queued', 'channel': 'slack'}

    async def notify_review(self, project_id: str, review_id: str, stage: str) -> dict:
        print(f'  [Slack] Review notification: {project_id} / {stage}')
        return {'status': 'queued', 'channel': 'slack'}
