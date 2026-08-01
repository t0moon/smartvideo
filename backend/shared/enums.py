from __future__ import annotations

from enum import Enum


class ProjectStage(str, Enum):
    CREATED = 'created'
    REQUIREMENT = 'requirement'
    STORYBOARD = 'storyboard'
    ASSET_PREP = 'asset_prep'
    SCENE_GEN = 'scene_gen'
    VIDEO_PROD = 'video_prod'
    REVIEW = 'review'
    PUBLISH = 'publish'
    DONE = 'done'
    ARCHIVED = 'archived'


class VideoStatus(str, Enum):
    PENDING = 'pending'
    GENERATING = 'generating'
    COMPLETED = 'completed'
    FAILED = 'failed'


class ReviewDecision(str, Enum):
    PENDING = 'pending'
    APPROVED = 'approved'
    REJECTED = 'rejected'
    PARTIAL_REVISION = 'partial_revision'


class AssetType(str, Enum):
    BRAND = 'brand'
    CHARACTER = 'character'
    VOICE = 'voice'
    PROMPT = 'prompt'
    TEMPLATE = 'template'
    IMAGE = 'image'
    VIDEO = 'video'
    SUBTITLE = 'subtitle'
    BGM = 'bgm'  # 用户上传的配乐


class SkillType(str, Enum):
    REQUIREMENT = 'requirement'
    STORYBOARD = 'storyboard'
    CHARACTER = 'character'
    SCENE = 'scene'
    VIDEO = 'video'
    SUBTITLE = 'subtitle'
    REVIEW = 'review'
    PUBLISH = 'publish'
