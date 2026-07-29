"""Tests for workspace manager."""
from __future__ import annotations

import json
from pathlib import Path

from workspace.manager import WorkspaceManager
from shared.schemas import Scene


class TestWorkspace:
    def test_create_run(self, tmp_path: Path) -> None:
        mgr = WorkspaceManager(tmp_path)
        run_dir = mgr.create_run("test_proj", "run_001")
        assert run_dir.exists()
        assert run_dir.name == "run_001"

    def test_write_read_artifact(self, tmp_path: Path) -> None:
        mgr = WorkspaceManager(tmp_path)
        data = {"key": "value", "num": 42}
        mgr.write_artifact("p1", "r1", "test.json", data)
        result = mgr.read_artifact("p1", "r1", "test.json")
        assert result == data

    def test_artifacts_dir(self, tmp_path: Path) -> None:
        mgr = WorkspaceManager(tmp_path)
        d = mgr.artifacts_dir("p1", "r1")
        assert d.exists()

    def test_list_runs(self, tmp_path: Path) -> None:
        mgr = WorkspaceManager(tmp_path)
        mgr.create_run("p1", "run_a")
        mgr.create_run("p1", "run_b")
        runs = mgr.list_runs("p1")
        assert "run_a" in runs
        assert "run_b" in runs

    def test_cleanup_run(self, tmp_path: Path) -> None:
        mgr = WorkspaceManager(tmp_path)
        mgr.create_run("p1", "del_me")
        assert len(mgr.list_runs("p1")) == 1
        mgr.cleanup_run("p1", "del_me")
        assert len(mgr.list_runs("p1")) == 0
