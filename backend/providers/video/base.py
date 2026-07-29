from __future__ import annotations

from abc import ABC, abstractmethod


class BaseVideoProvider(ABC):
    name: str = 'base'

    @abstractmethod
    def generate_clip(self, prompt: str, **kwargs) -> str:
        raise NotImplementedError

    @abstractmethod
    def poll_status(self, task_id: str) -> str:
        raise NotImplementedError

    @abstractmethod
    def download_result(self, task_id: str, output_path: str) -> str:
        raise NotImplementedError
