from __future__ import annotations

import json
from typing import Any

from channels.base import BaseChannel


class WebhookChannel(BaseChannel):
    name = 'webhook'

    def __init__(self, webhook_url: str = '') -> None:
        self.webhook_url = webhook_url

    async def send_message(self, user_id: str, message: str) -> dict:
        print(f'  [Webhook] To {user_id}: {message[:80]}...')
        return {'status': 'sent', 'channel': 'webhook'}

    async def send_card(self, user_id: str, title: str, content: str, actions: list[dict] | None = None) -> dict:
        print(f'  [Webhook] Card to {user_id}: {title}')
        return {'status': 'sent', 'channel': 'webhook'}

    async def notify_review(self, project_id: str, review_id: str, stage: str) -> dict:
        title = f'Review Required: {stage}'
        content = f'Project {project_id} needs your review at stage: {stage}'
        print(f'  [Webhook] Review notification: {title}')
        return {'status': 'sent', 'channel': 'webhook'}
