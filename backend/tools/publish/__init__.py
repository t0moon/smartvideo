from __future__ import annotations

from abc import ABC, abstractmethod
from typing import Any


class BasePublisher(ABC):
    name: str = 'base'

    @abstractmethod
    async def publish(self, video_path: str, title: str, description: str = '', tags: list[str] | None = None) -> dict[str, Any]:
        raise NotImplementedError

    @abstractmethod
    async def check_status(self, publish_id: str) -> dict[str, Any]:
        raise NotImplementedError


class TikTokPublisher(BasePublisher):
    name = 'tiktok'

    async def publish(self, video_path: str, title: str, description: str = '', tags: list[str] | None = None) -> dict[str, Any]:
        print(f'  [TikTok] Publishing: {title}')
        return {'status': 'queued', 'platform': 'tiktok', 'publish_id': f'tt_{id(self)}', 'url': ''}

    async def check_status(self, publish_id: str) -> dict[str, Any]:
        return {'status': 'completed', 'publish_id': publish_id}


class YouTubePublisher(BasePublisher):
    name = 'youtube'

    async def publish(self, video_path: str, title: str, description: str = '', tags: list[str] | None = None) -> dict[str, Any]:
        print(f'  [YouTube] Publishing: {title}')
        return {'status': 'queued', 'platform': 'youtube', 'publish_id': f'yt_{id(self)}', 'url': ''}

    async def check_status(self, publish_id: str) -> dict[str, Any]:
        return {'status': 'completed', 'publish_id': publish_id}


class XiaoHongShuPublisher(BasePublisher):
    name = 'xiaohongshu'

    async def publish(self, video_path: str, title: str, description: str = '', tags: list[str] | None = None) -> dict[str, Any]:
        print(f'  [Xiaohongshu] Publishing: {title}')
        return {'status': 'queued', 'platform': 'xiaohongshu', 'publish_id': f'xhs_{id(self)}', 'url': ''}

    async def check_status(self, publish_id: str) -> dict[str, Any]:
        return {'status': 'completed', 'publish_id': publish_id}


def get_publisher(name: str) -> BasePublisher:
    publishers = {
        'tiktok': TikTokPublisher(),
        'youtube': YouTubePublisher(),
        'xiaohongshu': XiaoHongShuPublisher(),
    }
    return publishers.get(name, TikTokPublisher())
