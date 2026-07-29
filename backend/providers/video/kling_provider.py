from __future__ import annotations

import time
import requests
from pathlib import Path
from typing import Any

from app.config import (
    KLING_API_KEY,
    KLING_BASE_URL,
    KLING_MODEL,
    KLING_DURATION,
    KLING_ASPECT_RATIO,
    KLING_RESOLUTION,
    KLING_AUDIO,
    KLING_POLL_INTERVAL,
    KLING_POLL_TIMEOUT,
)
from .base import BaseVideoProvider


class KlingVideoProvider(BaseVideoProvider):
    """Kling text-to-video provider (new Kling AI API).

    Supports models such as ``kling-2.5-turbo`` and ``kling-3.0``.
    Async flow: submit task -> poll status -> download result.

    Default configuration is tuned for Kling 2.5 Turbo, silent output,
    720p, 16:9, 5 seconds.
    """

    name = 'kling'

    def __init__(self) -> None:
        self.api_key = KLING_API_KEY
        self.base_url = KLING_BASE_URL
        self.model = KLING_MODEL
        self.default_duration = KLING_DURATION
        self.default_aspect = KLING_ASPECT_RATIO
        self.default_resolution = KLING_RESOLUTION
        self.default_audio = KLING_AUDIO
        self.poll_interval = KLING_POLL_INTERVAL
        self.poll_timeout = KLING_POLL_TIMEOUT

    # ------------------------------------------------------------------
    # Public API
    # ------------------------------------------------------------------

    def generate_clip(self, prompt: str, **kwargs) -> str:
        """Submit a text-to-video generation task.

        Returns the task_id (or external_task_id) used for polling.
        """
        duration = kwargs.get('duration_sec', self.default_duration)
        aspect_ratio = kwargs.get('aspect_ratio', self.default_aspect)
        resolution = kwargs.get('resolution', self.default_resolution)
        audio = kwargs.get('audio', self.default_audio)
        callback_url = kwargs.get('callback_url', '')
        external_task_id = kwargs.get('external_task_id', '')
        watermark = kwargs.get('watermark', False)

        payload: dict[str, Any] = {
            'prompt': prompt,
            'settings': {
                'resolution': resolution,
                'aspect_ratio': aspect_ratio,
                'duration': int(duration),
                'audio': audio,
            },
            'options': {
                'watermark_info': {'enabled': bool(watermark)},
            },
        }

        if callback_url:
            payload['options']['callback_url'] = callback_url
        if external_task_id:
            payload['options']['external_task_id'] = external_task_id

        # New Kling API path: /text-to-video/{model}
        path = f'/text-to-video/{self.model}'
        resp = self._request('POST', path, json=payload)
        task_id = self._extract_field(resp, 'id')

        if not task_id:
            task_id = self._extract_field(resp, 'task_id')

        if not task_id:
            raise RuntimeError(f'Kling task creation failed: {resp}')

        print(f'  [Kling] Task created: {task_id}')
        return str(task_id)

    def poll_status(self, task_id: str) -> str:
        """Poll the task status.

        Returns: 'completed' | 'processing' | 'failed'
        """
        resp = self._request('GET', '/tasks', params={'task_ids': task_id})

        task = self._extract_task(resp, task_id)
        status = str(task.get('status', '')).lower()

        mapping = {
            'succeeded': 'completed',
            'succeed': 'completed',
            'completed': 'completed',
            'success': 'completed',
            'submitted': 'processing',
            'processing': 'processing',
            'running': 'processing',
            'queued': 'processing',
            'queuing': 'processing',
            'failed': 'failed',
            'error': 'failed',
        }

        return mapping.get(status, 'processing')

    def download_result(self, task_id: str, output_path: str, **kwargs) -> str:
        """Wait for task completion, then download the video to output_path."""
        start = time.time()

        while True:
            status = self.poll_status(task_id)

            if status == 'completed':
                video_url = self._get_video_url(task_id)
                if video_url:
                    self._download_file(video_url, output_path)
                    return output_path

                print(f'  [Kling] No video URL found for completed task {task_id}')
                return ''

            if status == 'failed':
                print(f'  [Kling] Task {task_id} failed')
                return ''

            elapsed = time.time() - start
            if elapsed > self.poll_timeout:
                print(f'  [Kling] Timeout after {elapsed:.0f}s for {task_id}')
                return ''

            print(f'  [Kling] Polling {task_id} ({elapsed:.0f}s elapsed, status={status})')
            time.sleep(self.poll_interval)

    # ------------------------------------------------------------------
    # Internal helpers
    # ------------------------------------------------------------------

    def _request(self, method: str, path: str, **kwargs) -> dict[str, Any]:
        """Make an authenticated request to the Kling API."""
        url = f'{self.base_url}{path}'
        headers = {
            'Authorization': f'Bearer {self.api_key}',
            'Content-Type': 'application/json',
        }

        timeout = kwargs.pop('timeout', 120)
        resp = requests.request(
            method, url, headers=headers, timeout=timeout, **kwargs
        )
        resp.raise_for_status()

        data = resp.json() if resp.text else {}
        return data if isinstance(data, dict) else {}

    def _extract_field(self, data: dict[str, Any], field: str) -> Any:
        """Extract a field from Kling API wrapped response {code, data, ...}."""
        inner = data.get('data', data)
        if isinstance(inner, dict):
            val = inner.get(field)
            if val is not None:
                return val
        return data.get(field)

    def _extract_task(self, data: dict[str, Any], task_id: str) -> dict[str, Any]:
        """Pick the target task from /tasks response (data may be a list)."""
        inner = data.get('data', data)

        if isinstance(inner, list):
            for t in inner:
                if isinstance(t, dict) and str(t.get('id')) == str(task_id):
                    return t
            # Fallback: first task
            if inner and isinstance(inner[0], dict):
                return inner[0]
            return {}

        if isinstance(inner, dict):
            return inner

        return {}

    def _get_video_url(self, task_id: str) -> str:
        """Extract the video download URL from the completed task."""
        resp = self._request('GET', '/tasks', params={'task_ids': task_id})
        task = self._extract_task(resp, task_id)

        outputs = task.get('outputs', [])
        if outputs and isinstance(outputs, list):
            for out in outputs:
                if isinstance(out, dict) and out.get('type') == 'video':
                    return out.get('url', '')
            # Fallback: first output with a url
            for out in outputs:
                if isinstance(out, dict) and out.get('url'):
                    return out.get('url')

        return ''

    def _download_file(self, url: str, output_path: str) -> None:
        """Download a file from URL to local path."""
        resp = requests.get(url, timeout=300)
        resp.raise_for_status()
        Path(output_path).parent.mkdir(parents=True, exist_ok=True)
        Path(output_path).write_bytes(resp.content)
        print(f'  [Kling] Downloaded: {output_path} ({len(resp.content)} bytes)')
