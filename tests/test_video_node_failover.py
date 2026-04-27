from pathlib import Path

from app.graph.nodes import video as video_mod


class _AlwaysFailProvider:
    def generate(self, scene_id, prompt, negative_prompt, *, duration_sec=5.0):  # type: ignore[no-untyped-def]
        raise RuntimeError("transient upstream error")


def _fake_placeholder(path: Path, duration: float, color: str = "0x000000") -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_bytes(b"fake")


def test_video_node_fallback_to_placeholder(tmp_path, monkeypatch) -> None:
    monkeypatch.setattr(video_mod, "ARTIFACTS_DIR", tmp_path)
    monkeypatch.setattr(video_mod, "ffmpeg_available", lambda: True)
    monkeypatch.setattr(video_mod, "resolve_video_provider", lambda _out_dir: _AlwaysFailProvider())
    monkeypatch.setattr(video_mod, "generate_placeholder_clip", _fake_placeholder)
    monkeypatch.setenv("VIDEO_FAILOVER_TO_PLACEHOLDER", "1")

    out = video_mod.node_generate_clips(
        {
            "scenes": [
                {
                    "id": "S01",
                    "duration_sec": 2.0,
                    "visual_prompt": "test prompt",
                    "negative_prompt": "",
                    "narration": "",
                }
            ],
            "artifact_run_id": "t1",
        }
    )

    assert not out.get("errors")
    assert "S01" in out["clips"]
    assert Path(out["clips"]["S01"]).is_file()
    assert "Fallback applied" in out["messages"][0].content


def test_video_node_can_disable_fallback(tmp_path, monkeypatch) -> None:
    monkeypatch.setattr(video_mod, "ARTIFACTS_DIR", tmp_path)
    monkeypatch.setattr(video_mod, "ffmpeg_available", lambda: True)
    monkeypatch.setattr(video_mod, "resolve_video_provider", lambda _out_dir: _AlwaysFailProvider())
    monkeypatch.setattr(video_mod, "generate_placeholder_clip", _fake_placeholder)
    monkeypatch.setenv("VIDEO_FAILOVER_TO_PLACEHOLDER", "0")

    out = video_mod.node_generate_clips(
        {
            "scenes": [
                {
                    "id": "S01",
                    "duration_sec": 2.0,
                    "visual_prompt": "test prompt",
                    "negative_prompt": "",
                    "narration": "",
                }
            ],
            "artifact_run_id": "t2",
        }
    )

    assert out.get("errors")
    assert "Scene S01 video generation failed" in out["errors"][0]["message"]
