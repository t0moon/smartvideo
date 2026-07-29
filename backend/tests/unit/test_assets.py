"""Tests for Asset Library and Workflow Engine."""
from __future__ import annotations

import yaml
from pathlib import Path

from assets.service import AssetService
from assets.repository import AssetRepository
from shared.schemas import Asset, AssetType
from app.config import WORKFLOWS_DIR


class TestAssetRepository:
    def test_save_and_get(self, tmp_path: Path) -> None:
        repo = AssetRepository(tmp_path)
        asset = Asset(asset_id="a1", project_id="p1", asset_type=AssetType.BRAND, name="Test Brand")
        repo.save(asset)
        got = repo.get("a1")
        assert got is not None
        assert got.name == "Test Brand"
        assert got.asset_type == AssetType.BRAND

    def test_list_by_type(self, tmp_path: Path) -> None:
        repo = AssetRepository(tmp_path)
        repo.save(Asset(asset_id="a1", project_id="p1", asset_type=AssetType.BRAND, name="B1"))
        repo.save(Asset(asset_id="a2", project_id="p1", asset_type=AssetType.PROMPT, name="P1"))
        repo.save(Asset(asset_id="a3", project_id="p2", asset_type=AssetType.BRAND, name="B2"))
        brands = repo.list_by_type(asset_type=AssetType.BRAND)
        assert len(brands) == 2
        p1_assets = repo.list_by_type(project_id="p1")
        assert len(p1_assets) == 2

    def test_search_by_tag(self, tmp_path: Path) -> None:
        repo = AssetRepository(tmp_path)
        repo.save(Asset(asset_id="a1", project_id="p1", asset_type=AssetType.BRAND, name="Nike", tags=["sport", "shoe"]))
        repo.save(Asset(asset_id="a2", project_id="p1", asset_type=AssetType.PROMPT, name="Adidas", tags=["sport", "apparel"]))
        results = repo.search_by_tag("sport")
        assert len(results) == 2
        results = repo.search_by_tag("shoe")
        assert len(results) == 1

    def test_delete(self, tmp_path: Path) -> None:
        repo = AssetRepository(tmp_path)
        repo.save(Asset(asset_id="a1", project_id="p1", asset_type=AssetType.BRAND, name="Del"))
        assert repo.get("a1") is not None
        repo.delete("a1")
        assert repo.get("a1") is None


class TestAssetService:
    def test_create_brand_asset(self, tmp_path: Path) -> None:
        svc = AssetService(AssetRepository(tmp_path))
        a = svc.create_brand_asset("p1", {"brand_name": "Nike", "product_description": "Just do it"})
        assert a.asset_type == AssetType.BRAND
        assert a.name == "Nike"

    def test_collect_project_assets(self, tmp_path: Path) -> None:
        svc = AssetService(AssetRepository(tmp_path))
        artifacts = {
            "brand_profile": {"brand_name": "CocaCola", "product_description": "Fizzy drink"},
            "storyboard": {
                "scenes": [
                    {"title": "Intro", "prompt": "A red can in the snow"},
                    {"title": "Action", "prompt": "People enjoying cola"},
                ]
            },
            "clips": {"scene_0": "/tmp/clip1.mp4", "scene_1": "/tmp/clip2.mp4"},
        }
        created = svc.collect_project_assets("p1", artifacts)
        assert len(created) >= 5
        types = [a.asset_type for a in created]
        assert AssetType.BRAND in types
        assert AssetType.PROMPT in types
        assert AssetType.VIDEO in types


class TestWorkflowYAML:
    def test_load_product_ad(self) -> None:
        path = WORKFLOWS_DIR / "product_ad_v1.yaml"
        assert path.exists(), f"Workflow file not found: {path}"
        with open(path, "r") as f:
            wf = yaml.safe_load(f)
        assert wf["name"] == "product_ad_v1"
        assert len(wf["stages"]) == 5
        assert wf["stages"][0]["id"] == "requirement"
        assert wf["stages"][-1]["id"] == "stitch"

    def test_stage_structure(self) -> None:
        path = WORKFLOWS_DIR / "product_ad_v1.yaml"
        with open(path, "r") as f:
            wf = yaml.safe_load(f)
        for stage in wf["stages"]:
            assert "id" in stage
            assert "agent" in stage
            assert stage.get("next") is None or "next" in stage
