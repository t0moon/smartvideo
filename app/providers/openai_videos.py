from __future__ import annotations

import time
from pathlib import Path
from typing import Any

import httpx
from httpx import Timeout

from app.media.ffmpeg import transcode_clip_for_concat_copy

_ALLOWED_SECONDS = (4, 8, 12)


def snap_openai_video_seconds(duration_sec: float) -> int:
    """OpenAI Videos API 仅允许有限时长档位。"""
    d = max(0.5, float(duration_sec))
    for s in _ALLOWED_SECONDS:
        if d <= s + 1e-6:
            return s
    return _ALLOWED_SECONDS[-1]


def _join_under_base(api_base: str, *parts: str) -> str:
    root = api_base.rstrip("/")
    tail = "/".join(p.strip("/") for p in parts)
    return f"{root}/{tail}"


class OpenAIVideosProvider:
    """OpenAI 兼容网关：POST /v1/videos → 轮询 GET /v1/videos/{id} → GET /v1/videos/{id}/content。"""

    def _headers(self) -> dict[str, str]:
        return {
            "Authorization": f"Bearer {self._api_key}",
            "Accept": "application/json",
        }

    def _create_job(self, client: httpx.Client, prompt: str, seconds: int) -> str:
        url = _join_under_base(self._api_base, "videos")
        payload: dict[str, Any] = {
            "prompt": prompt,
            "model": self._model,
            "seconds": str(seconds),
        }
        if (self._size or "").strip():
            payload["size"] = self._size.strip()
        r = client.post(url, headers={**self._headers(), "Content-Type": "application/json"}, json=payload)
        r.raise_for_status()
        data = r.json()
        vid = data.get("id")
        if not vid:
            raise RuntimeError(f"创建视频任务失败：响应无 id：{data}")
        return str(vid)

    def _retrieve(self, client: httpx.Client, video_id: str) -> dict[str, Any]:
        url = _join_under_base(self._api_base, "videos", video_id)
        r = client.get(url, headers=self._headers())
        r.raise_for_status()
        return r.json()

    def _wait_until_done(self, client: httpx.Client, video_id: str) -> None:
        deadline = time.monotonic() + self._poll_timeout
        while time.monotonic() < deadline:
            meta = self._retrieve(client, video_id)
            status = str(meta.get("status") or "").lower()
            if status == "completed":
                return
            if status == "failed":
                err = meta.get("error") or meta
                raise RuntimeError(f"视频生成失败：{err}")
            time.sleep(self._poll_interval)
        raise TimeoutError(f"等待视频完成超时（>{self._poll_timeout}s）：{video_id}")

    def _download_content(self, client: httpx.Client, video_id: str, raw_path: Path) -> None:
        url = _join_under_base(self._api_base, "videos", video_id, "content")
        dl_timeout = Timeout(60.0, read=self._download_read_timeout, write=60.0, pool=60.0)
        with client.stream(
            "GET",
            url,
            headers=self._headers(),
            follow_redirects=True,
            timeout=dl_timeout,
        ) as r:
            r.raise_for_status()
            raw_path.parent.mkdir(parents=True, exist_ok=True)
            with raw_path.open("wb") as f:
                for chunk in r.iter_bytes():
                    f.write(chunk)

    def __init__(
        self,
        *,
        api_base_url: str,
        api_key: str,
        model: str,
        work_dir: Path,
        size: str = "1280x720",
        poll_interval_sec: float = 3.0,
        poll_timeout_sec: float = 600.0,
        timeout_sec: float = 120.0,
        download_read_timeout_sec: float = 1200.0,
    ) -> None:
        self._api_base = api_base_url.rstrip("/")
        self._api_key = api_key
        self._model = model
        self._work_dir = work_dir
        self._size = size
        self._poll_interval = poll_interval_sec
        self._poll_timeout = poll_timeout_sec
        self._timeout = timeout_sec
        self._download_read_timeout = download_read_timeout_sec

    def generate(
        self,
        scene_id: str,
        prompt: str,
        negative_prompt: str,
        *,
        duration_sec: float = 5.0,
    ) -> str:
        full_prompt = prompt.strip()
        if negative_prompt.strip():
            full_prompt = f"{full_prompt}\n\nAvoid / negative: {negative_prompt.strip()}"

        seconds = snap_openai_video_seconds(duration_sec)
        safe_id = scene_id.replace("/", "_")
        raw_path = self._work_dir / f"{safe_id}.raw.download.mp4"
        out_path = self._work_dir / f"{safe_id}.mp4"

        limits = httpx.Limits(max_keepalive_connections=5, max_connections=10)
        with httpx.Client(timeout=self._timeout, limits=limits) as client:
            video_id = self._create_job(client, full_prompt, seconds)
            self._wait_until_done(client, video_id)
            self._download_content(client, video_id, raw_path)

        transcode_clip_for_concat_copy(raw_path, out_path)
        try:
            raw_path.unlink(missing_ok=True)
        except OSError:
            pass
        return str(out_path.resolve())
