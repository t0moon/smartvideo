from __future__ import annotations

import base64
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
        """Submit a video generation task (text-to-video or image-to-video).

        When ``reference_image`` kwarg is provided (local path or URL), the
        image-to-video endpoint is used for motion-driven generation from a
        reference frame.  Otherwise the text-to-video endpoint is used.

        Returns the task_id used for polling.
        """
        duration = self._align_duration(kwargs.get('duration_sec', self.default_duration))
        aspect_ratio = kwargs.get('aspect_ratio', self.default_aspect)
        resolution = kwargs.get('resolution', self.default_resolution)
        audio = kwargs.get('audio', self.default_audio)
        callback_url = kwargs.get('callback_url', '')
        external_task_id = kwargs.get('external_task_id', '')
        watermark = kwargs.get('watermark', False)
        reference_image = kwargs.get('reference_image', '')

        settings: dict[str, Any] = {
            'resolution': resolution,
            'aspect_ratio': aspect_ratio,
            'duration': int(duration),
            'audio': audio,
        }
        options: dict[str, Any] = {'watermark_info': {'enabled': bool(watermark)}}
        if callback_url:
            options['callback_url'] = callback_url
        if external_task_id:
            options['external_task_id'] = external_task_id

        # ── Image-to-video path ─────────────────────────────────────────
        if reference_image:
            image_payload = self._prepare_image(reference_image)
            path = f'/image-to-video/{self.model}'
            payload: dict[str, Any] = {
                'image': image_payload,
                'settings': settings,
                'options': options,
            }
            if prompt and prompt.strip():
                payload['prompt'] = prompt.strip()
            print(f'  [Kling] Image-to-video task (ref: {reference_image[:60]}...)')
        else:
            path = f'/text-to-video/{self.model}'
            payload = {'prompt': prompt, 'settings': settings, 'options': options}

        resp = self._request('POST', path, json=payload)
        task_id = self._extract_field(resp, 'id')
        if not task_id:
            task_id = self._extract_field(resp, 'task_id')
        if not task_id:
            raise RuntimeError(f'Kling task creation failed: {resp}')

        print(f'  [Kling] Task created: {task_id}')
        return str(task_id)

    def _align_duration(self, duration) -> int:
        """Kling 2.5 Turbo only accepts duration ∈ {5, 10} seconds.

        Align any requested duration to the nearest supported bucket so callers
        (e.g. scene shots of 3s/4s) don't trigger a 400 from the API.
        """
        try:
            d = int(round(float(duration)))
        except (TypeError, ValueError):
            d = self.default_duration
        aligned = 5 if d <= 5 else 10
        if aligned != d:
            print(f'  [Kling] duration {d}s aligned to {aligned}s (Kling 2.5 Turbo supports only 5/10s)')
        return aligned

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

    def _prepare_image(self, image_ref: str) -> str:
        """Return a Kling-compatible image payload from *image_ref*.

        - URLs (http/https) are passed through as-is.
        - Local file paths are base64-encoded with a MIME prefix so Kling
          can decode them without storing them in a public bucket first.
        """
        if image_ref.startswith(('http://', 'https://')):
            return image_ref
        img_path = Path(image_ref)
        if not img_path.exists():
            raise FileNotFoundError(f'Reference image not found: {image_ref}')
        raw = img_path.read_bytes()
        ext = img_path.suffix.lower().lstrip('.')
        mime_map = {'jpg': 'jpeg', 'jpeg': 'jpeg', 'png': 'png', 'webp': 'webp'}
        mime = mime_map.get(ext, 'png')
        b64 = base64.b64encode(raw).decode('ascii')
        return f'data:image/{mime};base64,{b64}'

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
        if not resp.ok:
            # Surface the real API error body for root-cause diagnosis (e.g. 400 from Kling).
            print(f'  [Kling][HTTP {resp.status_code}] {resp.text[:500]}')
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
