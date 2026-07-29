"""Tests for Runtime State Machine + Executor + Scheduler + Planner + Checkpoint."""
from __future__ import annotations

from pathlib import Path

from runtime.state_machine import WorkflowStateMachine, StageNode, StageState
from runtime.planner import WorkflowPlanner
from runtime.checkpoint import CheckpointManager
from workspace.manager import WorkspaceManager
from project.service import ProjectService


class TestStageNode:
    def test_create(self) -> None:
        node = StageNode("test", {"key": "val"})
        assert node.stage_id == "test"
        assert node.state == StageState.PENDING

    def test_lifecycle(self) -> None:
        node = StageNode("s1", {})
        node.start()
        assert node.state == StageState.RUNNING
        assert node.started_at is not None
        node.complete({"result": "ok"})
        assert node.state == StageState.COMPLETED
        assert node.output == {"result": "ok"}

    def test_fail(self) -> None:
        node = StageNode("s1", {})
        node.start()
        node.fail("something went wrong")
        assert node.state == StageState.FAILED
        assert node.error == "something went wrong"

    def test_pause_resume(self) -> None:
        node = StageNode("s1", {})
        node.pause()
        assert node.state == StageState.PAUSED
        node.resume()
        assert node.state == StageState.RUNNING


class TestWorkflowStateMachine:
    def test_add_stage(self) -> None:
        sm = WorkflowStateMachine()
        sm.add_stage("s1", {})
        assert sm.get_stage("s1") is not None

    def test_add_edge(self) -> None:
        sm = WorkflowStateMachine()
        sm.add_stage("s1", {})
        sm.add_stage("s2", {})
        sm.add_edge("s1", "s2")
        assert sm.get_next_stages("s1") == ["s2"]

    def test_get_ordered_stages(self) -> None:
        sm = WorkflowStateMachine()
        sm.add_stage("a", {})
        sm.add_stage("b", {})
        sm.add_stage("c", {})
        sm.add_edge("a", "b")
        sm.add_edge("b", "c")
        ordered = sm.get_ordered_stages()
        assert ordered == ["a", "b", "c"]

    def test_first_stage(self) -> None:
        sm = WorkflowStateMachine()
        sm.add_stage("x", {})
        sm.add_stage("y", {})
        sm.add_edge("x", "y")
        assert sm.get_first_stage() == "x"

    def test_is_completed(self) -> None:
        sm = WorkflowStateMachine()
        n1 = sm.add_stage("a", {})
        n1.complete({})
        assert sm.is_completed() is True

    def test_is_paused(self) -> None:
        sm = WorkflowStateMachine()
        sm.add_stage("a", {})
        sm.pause_stage("a")
        assert sm.is_paused() is True

    def test_to_dict(self) -> None:
        sm = WorkflowStateMachine("test_wf")
        sm.add_stage("a", {"agent": "llm"})
        d = sm.to_dict()
        assert d["workflow_name"] == "test_wf"
        assert "a" in d["stages"]


class TestPlanner:
    def test_get_next(self) -> None:
        planner = WorkflowPlanner({"a": ["b"], "b": []})
        assert planner.get_next("a", {}) == "b"
        assert planner.get_next("b", {}) is None

    def test_parallel_targets(self) -> None:
        planner = WorkflowPlanner({"a": ["b", "c"]})
        targets = planner.get_parallel_targets("a")
        assert len(targets) == 2

    def test_should_pause(self) -> None:
        node = StageNode("r", {"pause_for_review": True})
        assert WorkflowPlanner.should_pause(node) is True
        node2 = StageNode("s", {})
        assert WorkflowPlanner.should_pause(node2) is False


class TestCheckpoint:
    def test_save_and_load(self, tmp_path: Path) -> None:
        mgr = WorkspaceManager(tmp_path)
        mgr.create_run("p1", "run_1")

        sm = WorkflowStateMachine("test_wf")
        sm.add_stage("a", {})
        sm.add_edge("a", "b")
        sm.start_stage("a")
        sm.complete_stage("a", {"ok": True})

        cp = CheckpointManager()
        cp.save("p1", sm, run_id="run_1")

        loaded = cp.load("p1", run_id="run_1")
        assert loaded is not None
        assert loaded.workflow_name == "test_wf"
        assert loaded.get_stage("a") is not None
        assert loaded.get_stage("a").state == StageState.COMPLETED

    def test_list_checkpoints(self, tmp_path: Path) -> None:
        mgr = WorkspaceManager(tmp_path)
        mgr.create_run("p1", "run_1")
        mgr.write_artifact("p1", "run_1", "checkpoint.json", {"test": True})
        cp = CheckpointManager()
        cps = cp.list_checkpoints("p1")
        assert len(cps) > 0
