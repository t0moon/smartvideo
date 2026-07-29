from __future__ import annotations

from datetime import datetime, timezone
from typing import Any
from pydantic import BaseModel, Field

from shared.enums import ProjectStage, ReviewDecision, VideoStatus, AssetType


# ©¤©¤ Project ©¤©¤©¤©¤©¤©¤©¤©¤©¤©¤©¤©¤©¤©¤©¤©¤©¤©¤©¤©¤©¤©¤©¤©¤©¤©¤©¤©¤©¤©¤©¤©¤©¤©¤©¤©¤©¤©¤©¤©¤©¤©¤©¤©¤©¤©¤©¤©¤©¤©¤

class ProjectCreate(BaseModel):
    name: str = Field(..., min_length=1, max_length=200)
    brief: str = Field(default='', max_length=10000)
    workflow_name: str = 'product_ad'


class Project(BaseModel):
    project_id: str
    name: str
    brief: str = ''
    workflow_name: str = 'product_ad'
    stage: ProjectStage = ProjectStage.CREATED
    created_at: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))
    updated_at: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))
    archived_at: datetime | None = None
    meta: dict[str, Any] = Field(default_factory=dict)


# ©¤©¤ Requirement / VideoSpec ©¤©¤©¤©¤©¤©¤©¤©¤©¤©¤©¤©¤©¤©¤©¤©¤©¤©¤©¤©¤©¤©¤©¤©¤©¤©¤©¤©¤©¤©¤©¤©¤©¤©¤

class VideoSpec(BaseModel):
    duration_sec: int = 30
    style: str = ''
    brand: str = ''
    platform: str = ''
    character_type: str = ''
    use_digital_human: bool = False
    voice_over: str = ''
    subtitle_enabled: bool = True
    raw_brief: str = ''
    extra: dict[str, Any] = Field(default_factory=dict)


# ©¤©¤ Storyboard / Scene / Shot ©¤©¤©¤©¤©¤©¤©¤©¤©¤©¤©¤©¤©¤©¤©¤©¤©¤©¤©¤©¤©¤©¤©¤©¤©¤©¤©¤©¤©¤©¤©¤©¤

class Shot(BaseModel):
    shot_id: str = ''
    description: str = ''
    duration_sec: int = 5
    camera: str = ''
    camera_motion: str = ''
    prompt: str = ''
    sfx: str = ''
    narration: str = ''
    shot_type: str = ''


class Scene(BaseModel):
    scene_id: str = ''
    title: str = ''
    description: str = ''
    duration_sec: int = 10
    shots: list[Shot] = Field(default_factory=list)
    prompt: str = ''
    reference_image: str = ''


class Storyboard(BaseModel):
    storyboard_id: str = ''
    project_id: str = ''
    scenes: list[Scene] = Field(default_factory=list)
    style_notes: str = ''
    pacing: str = ''
    total_duration_sec: int = 0


# ©¤©¤ Brand ©¤©¤©¤©¤©¤©¤©¤©¤©¤©¤©¤©¤©¤©¤©¤©¤©¤©¤©¤©¤©¤©¤©¤©¤©¤©¤©¤©¤©¤©¤©¤©¤©¤©¤©¤©¤©¤©¤©¤©¤©¤©¤©¤©¤©¤©¤©¤©¤©¤©¤©¤©¤

class BrandProfile(BaseModel):
    brand_name: str = ''
    product_name: str = ''
    product_description: str = ''
    industry: str = ''
    target_audience: str = ''
    brand_tone: str = ''
    key_selling_points: list[str] = Field(default_factory=list)
    colors: list[str] = Field(default_factory=list)
    logo_url: str = ''
    reference_urls: list[str] = Field(default_factory=list)
    competitors: list[str] = Field(default_factory=list)
    uncertain_fields: list[str] = Field(default_factory=list)
    extra: dict[str, Any] = Field(default_factory=dict)


# ©¤©¤ Asset ©¤©¤©¤©¤©¤©¤©¤©¤©¤©¤©¤©¤©¤©¤©¤©¤©¤©¤©¤©¤©¤©¤©¤©¤©¤©¤©¤©¤©¤©¤©¤©¤©¤©¤©¤©¤©¤©¤©¤©¤©¤©¤©¤©¤©¤©¤©¤©¤©¤©¤©¤©¤

class Asset(BaseModel):
    asset_id: str = ''
    project_id: str = ''
    asset_type: AssetType
    name: str = ''
    description: str = ''
    file_path: str = ''
    metadata: dict[str, Any] = Field(default_factory=dict)
    tags: list[str] = Field(default_factory=list)
    created_at: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))


# ©¤©¤ Review ©¤©¤©¤©¤©¤©¤©¤©¤©¤©¤©¤©¤©¤©¤©¤©¤©¤©¤©¤©¤©¤©¤©¤©¤©¤©¤©¤©¤©¤©¤©¤©¤©¤©¤©¤©¤©¤©¤©¤©¤©¤©¤©¤©¤©¤©¤©¤©¤©¤©¤©¤

class ReviewTask(BaseModel):
    review_id: str = ''
    project_id: str = ''
    stage: ProjectStage
    status: ReviewDecision = ReviewDecision.PENDING
    content: dict[str, Any] = Field(default_factory=dict)
    comments: list[dict[str, Any]] = Field(default_factory=list)
    created_at: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))
    resolved_at: datetime | None = None
    reviewer: str = ''


# ©¤©¤ Workflow ©¤©¤©¤©¤©¤©¤©¤©¤©¤©¤©¤©¤©¤©¤©¤©¤©¤©¤©¤©¤©¤©¤©¤©¤©¤©¤©¤©¤©¤©¤©¤©¤©¤©¤©¤©¤©¤©¤©¤©¤©¤©¤©¤©¤©¤©¤©¤©¤©¤

class WorkflowState(BaseModel):
    project_id: str = ''
    current_stage: ProjectStage = ProjectStage.CREATED
    video_spec: VideoSpec | None = None
    storyboard: Storyboard | None = None
    brand_profile: BrandProfile | None = None
    scenes: list[Scene] = Field(default_factory=list)
    clips: dict[str, str] = Field(default_factory=dict)
    video_paths: dict[str, str] = Field(default_factory=dict)
    final_video_path: str = ''
    errors: list[dict[str, Any]] = Field(default_factory=list)
    paused: bool = False
    meta: dict[str, Any] = Field(default_factory=dict)

