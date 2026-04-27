import json

import pytest

from app.remake_clips import _load_scenes


def test_load_scenes_array() -> None:
    raw = json.loads(
        '[{"id":"S01","duration_sec":2,"visual_prompt":"a","negative_prompt":"","narration":""}]'
    )
    out = _load_scenes(raw)
    assert len(out) == 1
    assert out[0]["id"] == "S01"


def test_load_scenes_wrapped() -> None:
    raw = {"scenes": [{"id": "S01", "duration_sec": 2, "visual_prompt": "x"}]}
    out = _load_scenes(raw)
    assert out[0]["id"] == "S01"


def test_load_scenes_rejects_bad_duration() -> None:
    raw = [{"id": "S01", "duration_sec": 0, "visual_prompt": "x"}]
    with pytest.raises(ValueError, match="duration"):
        _load_scenes(raw)
