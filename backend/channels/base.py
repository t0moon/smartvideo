from __future__ import annotations

from typing import Any
from abc import ABC, abstractmethod


class BaseChannel(ABC):
    name: str = 'base'

    @abstractmethod
    async def send_message(self, user_id: str, message: str) -> dict:
        raise NotImplementedError

    @abstractmethod
    async def send_card(self, user_id: str, title: str, content: str, actions: list[dict] | None = None) -> dict:
        raise NotImplementedError

    @abstractmethod
    async def notify_review(self, project_id: str, review_id: str, stage: str) -> dict:
        raise NotImplementedError
