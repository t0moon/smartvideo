from __future__ import annotations

import asyncio
import shutil
from abc import ABC, abstractmethod
from datetime import datetime, timezone
from pathlib import Path
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


class LocalPublisher(BasePublisher):
    """Export final video to a publish-ready output directory."""

    name = 'local'

    def __init__(self, output_dir: str | None = None) -> None:
        self.output_dir = Path(output_dir) if output_dir else None

    async def publish(self, video_path: str, title: str, description: str = '', tags: list[str] | None = None) -> dict[str, Any]:
        src = Path(video_path)
        if not src.exists():
            return {'status': 'error', 'message': f'Source file not found: {video_path}'}

        # Default output dir: ../outputs/publish/
        out_root = self.output_dir or src.parent.parent.parent / 'outputs' / 'publish'
        out_root.mkdir(parents=True, exist_ok=True)

        timestamp = datetime.now(timezone.utc).strftime('%Y%m%d_%H%M%S')
        safe_title = ''.join(c if c.isalnum() or c in '-_' else '_' for c in title)[:40]
        dst_name = f"{timestamp}_{safe_title}.mp4"
        dst = out_root / dst_name

        shutil.copy2(src, dst)
        size_mb = dst.stat().st_size / (1024 * 1024)

        result = {
            'status': 'completed',
            'platform': 'local',
            'publish_id': dst_name,
            'output_path': str(dst),
            'size_mb': round(size_mb, 2),
            'title': title,
            'published_at': datetime.now(timezone.utc).isoformat(),
        }
        print(f'  [Local] Published: {dst} ({size_mb:.1f} MB)')
        return result

    async def check_status(self, publish_id: str) -> dict[str, Any]:
        return {'status': 'completed', 'publish_id': publish_id}


def get_publisher(name: str = 'local') -> BasePublisher:
    publishers = {
        'local': LocalPublisher(),
        'tiktok': TikTokPublisher(),
        'youtube': YouTubePublisher(),
        'xiaohongshu': XiaoHongShuPublisher(),
    }
    return publishers.get(name, LocalPublisher())


def publish_local(video_path: str, title: str = 'SmartVideo Output') -> dict[str, Any]:
    """Synchronous convenience wrapper for local export."""
    pub = get_publisher('local')
    return asyncio.get_event_loop().run_until_complete(
        pub.publish(video_path, title)
    )
