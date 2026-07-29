from __future__ import annotations

import subprocess
import tempfile
from pathlib import Path

from .base import BaseVideoProvider


class PlaceholderVideoProvider(BaseVideoProvider):
    name = 'placeholder'

    def generate_clip(self, prompt: str, **kwargs) -> str:
        import uuid
        task_id = f'placeholder_{uuid.uuid4().hex[:8]}'
        return task_id

    def poll_status(self, task_id: str) -> str:
        return 'completed'

    def download_result(self, task_id: str, output_path: str, **kwargs) -> str:
        duration_sec = kwargs.get('duration_sec', 5)
        size = kwargs.get('size', '1280x720')
        color = kwargs.get('color', 'blue')

        cmd = [
            'ffmpeg', '-y',
            '-f', 'lavfi',
            '-i', f'color=c={color}:s={size}:d={duration_sec}:r=24',
            '-pix_fmt', 'yuv420p',
            '-c:v', 'libx264',
            '-preset', 'ultrafast',
            output_path,
        ]
        subprocess.run(cmd, capture_output=True, timeout=30)
        return output_path

