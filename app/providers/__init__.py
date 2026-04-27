"""视频生成供应商。"""

from app.providers.factory import build_video_provider, resolve_video_provider
from app.providers.http_video import HttpVideoProvider
from app.providers.openai_videos import OpenAIVideosProvider
from app.providers.video_base import VideoProvider

__all__ = [
    "HttpVideoProvider",
    "OpenAIVideosProvider",
    "VideoProvider",
    "build_video_provider",
    "resolve_video_provider",
]
