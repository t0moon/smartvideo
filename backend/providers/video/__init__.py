from __future__ import annotations

from app.config import VIDEO_PROVIDER
from .base import BaseVideoProvider
from .placeholder import PlaceholderVideoProvider
from .kling_provider import KlingVideoProvider


def get_video_provider() -> BaseVideoProvider:
    if VIDEO_PROVIDER == 'kling':
        return KlingVideoProvider()
    elif VIDEO_PROVIDER == 'placeholder':
        return PlaceholderVideoProvider()
    return PlaceholderVideoProvider()
