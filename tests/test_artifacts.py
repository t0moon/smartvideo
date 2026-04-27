import re

from app.artifacts import new_artifact_run_id, write_artifact_json


def test_new_artifact_run_id_format() -> None:
    rid = new_artifact_run_id()
    assert re.match(r"^\d{8}_\d{6}$", rid)


def test_write_artifact_json(tmp_path, monkeypatch) -> None:
    monkeypatch.setattr("app.artifacts.ARTIFACTS_DIR", tmp_path)
    p = write_artifact_json("20260101_120000", "x.json", {"a": 1})
    assert p is not None
    assert p.read_text(encoding="utf-8").strip().startswith("{")
