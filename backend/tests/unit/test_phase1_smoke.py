"""Basic smoke tests for Phase 1 MVP."""
from __future__ import annotations

import pytest
from pathlib import Path

from project.repository import ProjectRepository
from project.service import ProjectService
from shared.schemas import ProjectCreate, VideoSpec, Storyboard, Scene
from shared.enums import ProjectStage as PS


class TestProject:
    def test_create_project(self, tmp_path: Path) -> None:
        repo = ProjectRepository(tmp_path)
        data = ProjectCreate(name="Test", brief="test brief")
        proj = repo.create(data)
        assert proj.project_id.startswith("proj_")
        assert proj.name == "Test"
        assert proj.stage == PS.CREATED

    def test_get_project(self, tmp_path: Path) -> None:
        repo = ProjectRepository(tmp_path)
        data = ProjectCreate(name="Get Test", brief="get me")
        proj = repo.create(data)
        got = repo.get(proj.project_id)
        assert got.name == "Get Test"
        assert got.project_id == proj.project_id

    def test_list_projects(self, tmp_path: Path) -> None:
        repo = ProjectRepository(tmp_path)
        repo.create(ProjectCreate(name="A"))
        repo.create(ProjectCreate(name="B"))
        all_p = repo.list_all()
        assert len(all_p) == 2

    def test_update_stage(self, tmp_path: Path) -> None:
        repo = ProjectRepository(tmp_path)
        proj = repo.create(ProjectCreate(name="Update"))
        repo.update(proj.project_id, {"stage": PS.REQUIREMENT})
        got = repo.get(proj.project_id)
        assert got.stage == PS.REQUIREMENT

    def test_delete_project(self, tmp_path: Path) -> None:
        repo = ProjectRepository(tmp_path)
        proj = repo.create(ProjectCreate(name="Del"))
        repo.delete(proj.project_id)
        assert len(repo.list_all()) == 0


class TestService:
    def test_service_create_and_list(self) -> None:
        svc = ProjectService()
        proj = svc.create_project("Svc Test", "brief")
        assert proj.project_id
        projects = svc.list_projects()
        ids = [p.project_id for p in projects]
        assert proj.project_id in ids

    def test_service_advance_stage(self) -> None:
        svc = ProjectService()
        proj = svc.create_project("Stage Test", "brief")
        svc.advance_stage(proj.project_id, PS.REQUIREMENT)
        got = svc.get_project(proj.project_id)
        assert got.stage == PS.REQUIREMENT


class TestSchemas:
    def test_video_spec_defaults(self) -> None:
        spec = VideoSpec()
        assert spec.duration_sec == 30
        assert spec.subtitle_enabled is True

    def test_storyboard(self) -> None:
        scene = Scene(scene_id="s1", title="Intro", duration_sec=10)
        sb = Storyboard(scenes=[scene], total_duration_sec=10)
        assert len(sb.scenes) == 1
        assert sb.scenes[0].title == "Intro"

    def test_project_stage_enum(self) -> None:
        assert PS.CREATED.value == "created"
        assert PS.REQUIREMENT.value == "requirement"
        assert PS.DONE.value == "done"
