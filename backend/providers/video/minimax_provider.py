from __future__ import annotations

import time
import requests
from pathlib import Path
from typing import Any

from app.config import (
    MINIMAX_API_KEY,
    MINIMAX_BASE_URL,
    MINIMAX_MODEL,
    MINIMAX_DURATION,
    MINIMAX_ASPECT_RATIO,
    MINIMAX_RESOLUTION,
    MINIMAX_POLL_INTERVAL,
    MINIMAX_POLL_TIMEOUT,
)
from .base import BaseVideoProvider


class MiniMaxVideoProvider(BaseVideoProvider):
    """MiniMax video generation provider (video-01 / video-01-live2d)."""

    name = 'minimax'

    def __init__(self) -> None:
        self.api_key = MINIMAX_API_KEY
        self.base_url = MINIMAX_BASE_URL
        self.model = MINIMAX_MODEL
        self.default_duration = MINIMAX_DURATION
        self.default_aspect = MINIMAX_ASPECT_RATIO
        self.default_resolution = MINIMAX_RESOLUTION
        self.poll_interval = MINIMAX_POLL_INTERVAL
        self.poll_timeout = MINIMAX_POLL_TIMEOUT

    def generate_clip(self, prompt: str, **kwargs) -> str:
        duration = self._align_duration(kwargs.get('duration_sec', self.default_duration))
        reference_image = kwargs.get('reference_image', '')
        external_task_id = kwargs.get('external_task_id', '')

        payload: dict[str, Any] = {
            'model': self.model,
            'prompt': prompt.strip(),
            'prompt_optimizer': True,
            'duration': int(duration),
            'aspect_ratio': self.default_aspect,
            'resolution': self.default_resolution,
        }

        if reference_image:
            image_url = self._resolve_image(reference_image)
            if image_url:
                payload['first_frame_image'] = image_url
                if self.model == 'video-01':
                    payload['model'] = 'video-01-live2d'
                print(f'  [MiniMax] Image-to-video task (ref: {reference_image[:60]}...)')
            else:
                print(f'  [MiniMax] Reference image not usable, falling back to text-to-video')
        else:
            print(f'  [MiniMax] Text-to-video task (prompt: {prompt[:60]}...)')

        if external_task_id:
            payload['external_task_id'] = external_task_id

        resp = self._request('POST', '/v1/video_generation', json=payload)
        task_id = self._extract_task_id(resp)
        print(f'  [MiniMax] Task created: {task_id}')
        return str(task_id)

    def _align_duration(self, duration) -> int:
        try:
            d = int(round(float(duration)))
        except (TypeError, ValueError):
            d = self.default_duration
        d = max(2, min(d, 30))
        if d != int(duration):
            print(f'  [MiniMax] duration {duration}s clipped to {d}s (valid range: 2-30s)')
        return d

    def _resolve_image(self, image_ref: str) -> str:
        """Resolve reference to a URL. Returns '' for non-usable refs (text descriptions etc)."""
        if not image_ref or not image_ref.strip():
            return ''
        ri = image_ref.strip()
        if ri.startswith(('http://', 'https://')):
            return ri
        # Text descriptions contain Chinese chars — not a real path/URL
        if len(ri) > 15 and any('\u4e00' <= c <= '\u9fff' for c in ri):
            print(f'  [MiniMax] Reference is a text description, skipping: {ri[:60]}...')
            return ''
        img_path = Path(ri)
        if img_path.exists():
            print(f'  [MiniMax] Using local reference image: {ri}')
            return ri
        print(f'  [MiniMax] Reference not a reachable file/URL, skipping: {ri[:60]}...')
        return ''

    def poll_status(self, task_id: str) -> str:
        resp = self._request('GET', '/v1/query/video_generation', params={'task_id': task_id})
        status = str(resp.get('status', '')).lower()
        completed = {'success', 'succeeded', 'completed', 'done'}
        processing = {'preparing', 'queueing', 'processing', 'running'}
        failed = {'fail', 'failed', 'error', 'unknown'}
        if status in completed:
            return 'completed'
        if status in failed:
            print(f'  [MiniMax] Task {task_id} failed: {resp.get("base_resp", {})}')
            return 'failed'
        return 'processing'

    def download_result(self, task_id: str, output_path: str, **kwargs) -> str:
        start = time.time()
        while True:
            status = self.poll_status(task_id)
            if status == 'completed':
                video_url = self._get_video_url(task_id)
                if video_url:
                    self._download_file(video_url, output_path)
                    return output_path
                print(f'  [MiniMax] No video URL for completed task {task_id}')
                return ''
            if status == 'failed':
                return ''
            elapsed = time.time() - start
            if elapsed > self.poll_timeout:
                print(f'  [MiniMax] Timeout after {elapsed:.0f}s for {task_id}')
                return ''
            print(f'  [MiniMax] Polling {task_id} ({elapsed:.0f}s elapsed, status={status})')
            time.sleep(self.poll_interval)

    def _request(self, method: str, path: str, **kwargs) -> dict[str, Any]:
        url = f'{self.base_url}{path}'
        headers = {
            'Authorization': f'Bearer {self.api_key}',
            'Content-Type': 'application/json',
        }
        timeout = kwargs.pop('timeout', 120)
        resp = requests.request(method, url, headers=headers, timeout=timeout, **kwargs)
        if not resp.ok:
            print(f'  [MiniMax][HTTP {resp.status_code}] {resp.text[:500]}')
        resp.raise_for_status()
       data = resp.json() if resp.text else {}
        if isinstance(data, dict):
            # MiniMax v2 API wraps all responses in a {"data": {...}, "base_resp": {...}} envelope.
            # Unwrap the inner "data" so callers (poll_status, _get_video_url, etc.) can access
            # task_id / status / video_url directly.
            inner = data.get('data', data)
            return inner if isinstance(inner, dict) else data
        return {}

   def _extract_task_id(self, data: dict[str, Any]) -> str:
        base = data.get('base_resp', {})
        if isinstance(base, dict) and base.get('status_code') != 0:
            msg = base.get('status_msg', 'unknown error')
            raise RuntimeError(f'MiniMax API error: {msg}')
        task_id = data.get('task_id', '')
        if not task_id:
            raise RuntimeError(f'MiniMax task creation failed (no task_id): {data}')
        return task_id

    def _get_video_url(self, task_id: str) -> str:
        resp = self._request('GET', '/v1/query/video_generation', params={'task_id': task_id})
        video_url = resp.get('video_url', '')
        if video_url:
            return video_url
        return resp.get('cover_url', '')

    def _download_file(self, url: str, output_path: str) -> None:
        resp = requests.get(url, timeout=300)
        resp.raise_for_status()
        Path(output_path).parent.mkdir(parents=True, exist_ok=True)
        Path(output_path).write_bytes(resp.content)
        print(f'  [MiniMax] Downloaded: {output_path} ({len(resp.content)} bytes)')
