"""Tests for providers."""
from __future__ import annotations

import shutil

import pytest
from providers.video.base import BaseVideoProvider
from providers.video.placeholder import PlaceholderVideoProvider
from providers.video import get_video_provider


class TestVideoProvider:
    def test_placeholder_is_valid_provider(self) -> None:
        p = PlaceholderVideoProvider()
        assert isinstance(p, BaseVideoProvider)
        assert p.name == "placeholder"

    def test_placeholder_generates_task_id(self) -> None:
        p = PlaceholderVideoProvider()
        task = p.generate_clip("test prompt", duration_sec=5)
        assert task.startswith("placeholder_")

    def test_placeholder_polls_completed(self) -> None:
        p = PlaceholderVideoProvider()
        task = p.generate_clip("test")
        assert p.poll_status(task) == "completed"

    def test_factory_returns_placeholder(self) -> None:
        p = get_video_provider()
        assert isinstance(p, BaseVideoProvider)

    @pytest.mark.skipif(
        shutil.which("ffmpeg") is None,
        reason="ffmpeg not in PATH",
    )
    def test_download_result(self, tmp_path) -> None:
        p = PlaceholderVideoProvider()
        out = tmp_path / "clip.mp4"
        task = p.generate_clip("test")
        result = p.download_result(task, str(out), duration_sec=2, size="320x240", color="blue")
        assert result == str(out)
