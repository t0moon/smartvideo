"""End-to-end pipeline integration tests."""
from __future__ import annotations

import json
from pathlib import Path

from project.service import ProjectService
from project.repository import ProjectRepository
from workspace.manager import WorkspaceManager
from shared.schemas import ProjectStage
from shared.enums import ProjectStage as PS
from review.service import ReviewService
from assets.service import AssetService
from assets.repository import AssetRepository
from subagents.registry import SubagentRegistry
from subagents.executor import ParallelExecutor
from subagents.base import BaseSubagent
from tools.publish import get_publisher


class TestE2EPipeline:
    PATH = Path(__file__).parent.parent / "data" / "test_e2e"

    def setup_method(self) -> None:
        self.PATH.mkdir(parents=True, exist_ok=True)
        self.project_repo = ProjectRepository(self.PATH / "projects")
        self.workspace = WorkspaceManager(self.PATH / "workspace")
        self.assets = AssetService(AssetRepository(self.PATH / "assets"))

    def teardown_method(self) -> None:
        import shutil
        if self.PATH.exists():
            shutil.rmtree(self.PATH)

    def test_01_create_project(self) -> None:
        svc = ProjectService()
        proj = svc.create_project("E2E Test", "Test brief for E2E")
        assert proj.project_id
        assert proj.name == "E2E Test"
        assert proj.stage == PS.CREATED

    def test_02_project_lifecycle(self) -> None:
        svc = ProjectService()
        proj = svc.create_project("Lifecycle", "brief")
        stages = [PS.REQUIREMENT, PS.STORYBOARD, PS.SCENE_GEN, PS.VIDEO_PROD, PS.REVIEW, PS.PUBLISH, PS.DONE]
        for stage in stages:
            proj = svc.advance_stage(proj.project_id, stage)
            assert proj.stage == stage

    def test_03_asset_crud(self) -> None:
        svc = AssetService(AssetRepository(self.PATH / "assets"))
        a = svc.create_brand_asset("proj_1", {"brand_name": "TestBrand", "product_description": "E2E test"})
        assert a.asset_type.value == "brand"
        assert svc.get_asset(a.asset_id) is not None
        assert len(svc.list_assets(project_id="proj_1")) == 1

    def test_04_asset_search(self) -> None:
        svc = AssetService(AssetRepository(self.PATH / "assets"))
        svc.create_brand_asset("p1", {"brand_name": "Nike", "industry": "sport"})
        svc.create_brand_asset("p1", {"brand_name": "Adidas", "industry": "sport"})
        results = svc.search_assets("sport")
        assert len(results) == 2

    def test_05_review_workflow(self) -> None:
        svc = ReviewService()
        r1 = svc.create_requirement_review("proj_e2e", {"duration_sec": 30})
        r2 = svc.create_storyboard_review("proj_e2e", {"scenes": ["scene1"]})
        assert svc.is_project_blocked("proj_e2e") is True
        svc.approve(r1.review_id)
        assert svc.is_project_blocked("proj_e2e") is True
        svc.approve(r2.review_id)
        assert svc.is_project_blocked("proj_e2e") is False
        assert len(svc.list_by_project("proj_e2e")) == 2

    def test_06_subagent_registry(self) -> None:
        registry = SubagentRegistry()

        class MockAgent(BaseSubagent):
            name = "mock"
            async def execute(self, task, context):
                return {"result": "ok", "task": task}

        registry.register(MockAgent())
        assert "mock" in registry.list_names()

    def test_07_parallel_executor(self) -> None:
        executor = ParallelExecutor(max_workers=2)
        results = executor.run_parallel([
            lambda: {"id": 1, "value": "a"},
            lambda: {"id": 2, "value": "b"},
        ])
        assert len(results) == 2

    def test_08_publish_service(self) -> None:
        import asyncio
        pub = get_publisher("youtube")
        result = asyncio.run(pub.publish("/tmp/test.mp4", "Test Video"))
        assert result["status"] == "queued"
        assert result["platform"] == "youtube"

    def test_09_platform_publishers(self) -> None:
        import asyncio
        for name in ["tiktok", "youtube", "xiaohongshu"]:
            pub = get_publisher(name)
            result = asyncio.run(pub.publish("/tmp/v.mp4", "Title"))
            assert result["status"] == "queued"
            assert result["platform"] == name

    def test_10_full_asset_collection(self) -> None:
        svc = AssetService(AssetRepository(self.PATH / "assets"))
        artifacts = {
            "brand_profile": {"brand_name": "E2E", "product_description": "Full cycle"},
            "storyboard": {"scenes": [{"title": "Scene1", "prompt": "Prompt1"}, {"title": "Scene2", "prompt": "Prompt2"}]},
            "clips": {"scene_0": "/tmp/clip1.mp4"},
        }
        created = svc.collect_project_assets("proj_e2e", artifacts)
        assert len(created) >= 4
