"""Tests for Context Builder system."""
from __future__ import annotations

from pathlib import Path

from context.builder import ContextBuilder
from context.manager import ContextManager
from context.selector import ContextSelector
from context.schemas import StageContext, StageOutput
from project.service import ProjectService


class TestContextSchemas:
    def test_stage_context_defaults(self) -> None:
        ctx = StageContext(stage_id="test", project_id="p1")
        assert ctx.stage_id == "test"
        assert ctx.project_id == "p1"
        assert ctx.inputs == {}
        assert ctx.assets == []
        assert ctx.created_at is not None

    def test_stage_output_defaults(self) -> None:
        out = StageOutput(stage_id="s1", project_id="p1")
        assert out.outputs == {}
        assert out.error == ""


class TestContextSelector:
    def test_get_stage_config(self) -> None:
        sel = ContextSelector()
        config = sel.get_stage_config("requirement")
        assert "inputs" in config
        assert "produces" in config
        assert config["produces"] == ["video_spec"]

    def test_get_stage_config_unknown(self) -> None:
        sel = ContextSelector()
        config = sel.get_stage_config("nonexistent")
        assert config["inputs"] == []

    def test_storyboard_config(self) -> None:
        sel = ContextSelector()
        config = sel.get_stage_config("storyboard")
        assert config["inputs"] == ["video_spec"]
        assert config["produces"] == ["storyboard"]

    def test_video_gen_config(self) -> None:
        sel = ContextSelector()
        config = sel.get_stage_config("video_gen")
        assert config["inputs"] == ["scenes"]

    def test_review_config(self) -> None:
        sel = ContextSelector()
        config = sel.get_stage_config("review")
        assert config["inputs"] == ["video_spec", "storyboard", "clips"]
        assert "review" in config.get("providers", [])


class TestContextManager:
    def test_set_and_get(self) -> None:
        mgr = ContextManager()
        ctx = StageContext(stage_id="s1", project_id="p1")
        mgr.set(ctx)
        got = mgr.get("p1", "s1")
        assert got is not None
        assert got.stage_id == "s1"

    def test_invalidate(self) -> None:
        mgr = ContextManager()
        mgr.set(StageContext(stage_id="s1", project_id="p1"))
        mgr.set(StageContext(stage_id="s2", project_id="p1"))
        mgr.invalidate("p1", "s1")
        assert mgr.get("p1", "s1") is None
        assert mgr.get("p1", "s2") is not None

    def test_clear(self) -> None:
        mgr = ContextManager()
        mgr.set(StageContext(stage_id="s1", project_id="p1"))
        mgr.clear()
        assert mgr.get("p1", "s1") is None

    def test_invalidate_all(self) -> None:
        mgr = ContextManager()
        mgr.set(StageContext(stage_id="s1", project_id="p1"))
        mgr.set(StageContext(stage_id="s2", project_id="p2"))
        mgr.invalidate("p1")
        assert mgr.get("p1", "s1") is None
        assert mgr.get("p2", "s2") is not None


class TestContextBuilder:
    def test_build_basic(self) -> None:
        svc = ProjectService()
        proj = svc.create_project("Ctx Test", "test brief")
        builder = ContextBuilder()
        ctx = builder.build(proj.project_id, "requirement")
        assert ctx.stage_id == "requirement"
        assert ctx.project_id == proj.project_id
        assert ctx.project["name"] == "Ctx Test"
        assert "project" in ctx.config.get("inputs", [])

    def test_save_output(self) -> None:
        svc = ProjectService()
        proj = svc.create_project("Ctx Output", "brief")
        builder = ContextBuilder()
        out = builder.save_output(proj.project_id, "requirement", {"video_spec": {"duration_sec": 30, "style": "modern"}})
        assert out.stage_id == "requirement"
        assert out.outputs.get("video_spec") is not None

    def test_provider_results_in_context(self) -> None:
        svc = ProjectService()
        proj = svc.create_project("Ctx Provider", "brief")
        builder = ContextBuilder()
        ctx = builder.build(proj.project_id, "requirement")
        assert "project" in ctx.provider_outputs
        assert ctx.provider_outputs["project"]["project_id"] == proj.project_id

    def test_review_stage_providers(self) -> None:
        svc = ProjectService()
        proj = svc.create_project("Review Ctx", "brief")
        builder = ContextBuilder()
        ctx = builder.build(proj.project_id, "review")
        assert "review" in ctx.provider_outputs
        assert "is_blocked" in ctx.provider_outputs["review"]
