"""Phase 2 — YAML-driven pipeline engine tests.

These tests lock the orchestration behaviour implemented in
``runtime.workflow.WorkflowRuntime`` without invoking the LLM or any network
call (so they run offline). They verify that the workflow YAML graph is loaded
correctly, that resume() routes each Human-in-the-Loop pause stage to the right
next handler, and that the stage->handler map is complete.
"""
from __future__ import annotations

from runtime.workflow import WorkflowRuntime
from runtime.state_machine import WorkflowStateMachine


EXPECTED_CHAIN = [
    "requirement",
    "storyboard",
    "asset_prep",
    "scene_gen",
    "video_gen",
    "stitch",
    "publish",
]


class TestYamlGraph:
    def test_full_chain_traversal(self) -> None:
        wr = WorkflowRuntime()
        sm = wr._load_yaml("product_ad")
        assert sm.get_first_stage() == "requirement"

        chain: list[str] = []
        cur = sm.get_first_stage()
        while cur:
            chain.append(cur)
            nxt = sm.get_next_stages(cur)
            cur = nxt[0] if nxt else None
        assert chain == EXPECTED_CHAIN

    def test_asset_prep_between_storyboard_and_scene(self) -> None:
        wr = WorkflowRuntime()
        sm = wr._load_yaml("product_ad")
        assert sm.get_next_stages("storyboard") == ["asset_prep"]
        assert sm.get_next_stages("asset_prep") == ["scene_gen"]

    def test_publish_after_stitch(self) -> None:
        wr = WorkflowRuntime()
        sm = wr._load_yaml("product_ad")
        assert sm.get_next_stages("stitch") == ["publish"]
        assert sm.get_next_stages("publish") == []


class TestResumeRouting:
    """resume() resolves the next stage from the YAML `next` edges (with a
    hardcoded fallback when the YAML is unavailable)."""

    def test_requirement_routes_to_storyboard(self) -> None:
        wr = WorkflowRuntime()
        assert wr._route_next_stage("requirement", "product_ad") == "storyboard"

    def test_storyboard_routes_to_asset_prep(self) -> None:
        wr = WorkflowRuntime()
        assert wr._route_next_stage("storyboard", "product_ad") == "asset_prep"

    def test_asset_prep_routes_to_scene_gen(self) -> None:
        wr = WorkflowRuntime()
        assert wr._route_next_stage("asset_prep", "product_ad") == "scene_gen"

    def test_video_gen_routes_to_stitch(self) -> None:
        wr = WorkflowRuntime()
        assert wr._route_next_stage("video_gen", "product_ad") == "stitch"

    def test_unknown_pause_returns_none(self) -> None:
        wr = WorkflowRuntime()
        assert wr._route_next_stage("nonexistent", "product_ad") is None

    def test_fallback_when_yaml_missing(self) -> None:
        wr = WorkflowRuntime()
        # A workflow name that does not exist -> fallback map is used.
        assert wr._route_next_stage("requirement", "does_not_exist") == "storyboard"
        assert wr._route_next_stage("storyboard", "does_not_exist") == "asset_prep"
        assert wr._route_next_stage("asset_prep", "does_not_exist") == "scene_gen"
        assert wr._route_next_stage("video_gen", "does_not_exist") == "stitch"
        # Backward-compat: pre-v2 projects paused at video_review.
        assert wr._route_next_stage("video_review", "does_not_exist") == "stitch"


class TestHandlerMap:
    def test_all_stages_have_handlers(self) -> None:
        wr = WorkflowRuntime()
        handlers = wr._stage_handlers()
        for stage in EXPECTED_CHAIN:
            assert stage in handlers, f"missing handler for stage: {stage}"
            assert callable(handlers[stage])

    def test_handler_names_match_exec_convention(self) -> None:
        wr = WorkflowRuntime()
        handlers = wr._stage_handlers()
        assert handlers["requirement"].__name__ == "_exec_requirement"
        assert handlers["storyboard"].__name__ == "_exec_storyboard"
        assert handlers["asset_prep"].__name__ == "_exec_asset_prep"
        assert handlers["scene_gen"].__name__ == "_exec_scene_gen"
        assert handlers["video_gen"].__name__ == "_exec_video_gen"
        assert handlers["stitch"].__name__ == "_exec_stitch"
        assert handlers["publish"].__name__ == "_exec_publish"


class TestEngineEntrypoints:
    def test_v1_fallback_exists(self) -> None:
        wr = WorkflowRuntime()
        assert callable(getattr(wr, "run_pipeline"))

    def test_v2_yaml_engine_exists(self) -> None:
        wr = WorkflowRuntime()
        assert callable(getattr(wr, "run_pipeline_v2"))
