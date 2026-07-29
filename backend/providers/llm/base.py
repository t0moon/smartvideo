from __future__ import annotations

from abc import ABC, abstractmethod


class BaseLLMProvider(ABC):
    name: str = 'base'

    @abstractmethod
    def chat(self, messages: list[dict], **kwargs) -> str:
        raise NotImplementedError

    @abstractmethod
    def chat_structured(self, messages: list[dict], response_model: type, **kwargs) -> object:
        raise NotImplementedError
