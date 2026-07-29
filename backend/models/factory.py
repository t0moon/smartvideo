from __future__ import annotations

from typing import Any

from providers.llm import get_llm_provider
from providers.llm.base import BaseLLMProvider


class ModelRouter:
    def __init__(self) -> None:
        self._provider = get_llm_provider()

    def chat(self, messages: list[dict], **kwargs) -> str:
        return self._provider.chat(messages, **kwargs)

    def chat_structured(self, messages: list[dict], response_model: type, **kwargs) -> object:
        return self._provider.chat_structured(messages, response_model, **kwargs)
