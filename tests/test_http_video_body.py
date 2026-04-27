from app.providers.http_video import build_http_video_create_body


def test_build_veo_body_default(monkeypatch) -> None:
    monkeypatch.delenv("VIDEO_HTTP_BODY_MODE", raising=False)
    monkeypatch.setenv("VIDEO_ASPECT_RATIO", "16:9")
    b = build_http_video_create_body(
        scene_id="S01",
        prompt="牛飞上天了",
        negative_prompt="",
        duration_sec=5.0,
        model="veo3.1-fast-components",
    )
    assert b["prompt"] == "牛飞上天了"
    assert b["model"] == "veo3.1-fast-components"
    assert b["aspect_ratio"] == "16:9"
    assert b["enhance_prompt"] is True
    assert b["veo_fl_close"] is True
    assert "scene_id" not in b
    assert "images" not in b


def test_build_legacy_body(monkeypatch) -> None:
    monkeypatch.setenv("VIDEO_HTTP_BODY_MODE", "legacy")
    b = build_http_video_create_body(
        scene_id="S01",
        prompt="x",
        negative_prompt="y",
        duration_sec=5.0,
        model="m",
    )
    assert b["scene_id"] == "S01"
    assert b["negative_prompt"] == "y"
    assert b["duration_sec"] == 5.0
