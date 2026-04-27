from __future__ import annotations

from pathlib import Path
from typing import Optional

from app.config import (
    VIDEO_API_BASE_URL,
    VIDEO_API_KEY,
    VIDEO_API_PATH,
    VIDEO_DOWNLOAD_READ_TIMEOUT_SEC,
    VIDEO_HTTP_TIMEOUT,
    VIDEO_MODEL,
    VIDEO_POLL_INTERVAL_SEC,
    VIDEO_POLL_TIMEOUT_SEC,
    VIDEO_PROVIDER,
    VIDEO_REQUEST_TIMEOUT_SEC,
    VIDEO_SIZE,
    effective_video_api_base_url,
    effective_video_api_key,
)
from app.providers.http_video import HttpVideoProvider
from app.providers.openai_videos import OpenAIVideosProvider
from app.providers.video_base import VideoProvider


def resolve_video_provider(work_dir: Path) -> Optional[VideoProvider]:
    """占位模式返回 None，由 video 节点用 lavfi 生成片段（与现有节点逻辑一致）。"""
    mode = VIDEO_PROVIDER
    if mode in ("", "placeholder", "lavfi", "mock"):
        return None

    if mode in ("openai_videos", "openai", "videos"):
        base = effective_video_api_base_url()
        key = effective_video_api_key()
        if not base or not key:
            raise ValueError(
                "VIDEO_PROVIDER=openai_videos 需要可用的网关地址与密钥："
                "请设置 VIDEO_API_BASE_URL / VIDEO_API_KEY，或沿用 OPENAI_BASE_URL / OPENAI_API_KEY。"
            )
        if not (VIDEO_MODEL or "").strip():
            raise ValueError("VIDEO_PROVIDER=openai_videos 需要设置 VIDEO_MODEL（例如 sora-2）。")
        return OpenAIVideosProvider(
            api_base_url=base,
            api_key=key,
            model=VIDEO_MODEL.strip(),
            work_dir=work_dir,
            size=VIDEO_SIZE,
            poll_interval_sec=VIDEO_POLL_INTERVAL_SEC,
            poll_timeout_sec=VIDEO_POLL_TIMEOUT_SEC,
            timeout_sec=VIDEO_REQUEST_TIMEOUT_SEC,
            download_read_timeout_sec=VIDEO_DOWNLOAD_READ_TIMEOUT_SEC,
        )

    if mode in ("http", "http_json", "custom"):
        base = (VIDEO_API_BASE_URL or "").strip() or (effective_video_api_base_url() or "")
        key = (VIDEO_API_KEY or "").strip() or (effective_video_api_key() or "")
        if not base or not key:
            raise ValueError(
                "VIDEO_PROVIDER=http 需要 VIDEO_API_BASE_URL 与 VIDEO_API_KEY（或回退的 OPENAI_*）。"
            )
        return HttpVideoProvider(
            work_dir=work_dir,
            base_url=base,
            api_key=key,
            api_path=VIDEO_API_PATH,
            model=VIDEO_MODEL,
            timeout_sec=VIDEO_HTTP_TIMEOUT,
            poll_interval_sec=VIDEO_POLL_INTERVAL_SEC,
            poll_timeout_sec=VIDEO_POLL_TIMEOUT_SEC,
            download_read_timeout_sec=VIDEO_DOWNLOAD_READ_TIMEOUT_SEC,
        )

    raise ValueError(f"未知的 VIDEO_PROVIDER：{mode!r}")


# 与「构建用于本 run 工作目录的 provider」语义一致，便于节点侧命名
build_video_provider = resolve_video_provider
