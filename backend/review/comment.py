from __future__ import annotations

import uuid
from datetime import datetime, timezone
from enum import Enum
from typing import Any

from pydantic import BaseModel, Field


class ReviewStage(str, Enum):
    REQUIREMENT = 'requirement'
    STORYBOARD = 'storyboard'
    ASSET_PREP = 'asset_prep'
    VIDEO_REVIEW = 'video_review'


class ReviewStatus(str, Enum):
    PENDING = 'pending'
    APPROVED = 'approved'
    REJECTED = 'rejected'
    PARTIAL_REVISION = 'partial_revision'


class Comment(BaseModel):
    comment_id: str = Field(default_factory=lambda: uuid.uuid4().hex[:12])
    text: str
    action: str = 'comment'  # approve | reject | comment | request_change
    created_at: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))
    reviewer: str = ''


class ReviewRecord(BaseModel):
    review_id: str = Field(default_factory=lambda: uuid.uuid4().hex[:12])
    project_id: str
    stage: ReviewStage
    status: ReviewStatus = ReviewStatus.PENDING
    content: dict[str, Any] = Field(default_factory=dict)
    comments: list[Comment] = Field(default_factory=list)
    created_at: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))
    resolved_at: datetime | None = None
    reviewer: str = ''

    def approve(self, reviewer: str = '', comment_text: str = '') -> None:
        self.status = ReviewStatus.APPROVED
        self.resolved_at = datetime.now(timezone.utc)
        self.reviewer = reviewer
        if comment_text:
            self.comments.append(Comment(text=comment_text, action='approve', reviewer=reviewer))

    def reject(self, reviewer: str = '', comment_text: str = '') -> None:
        self.status = ReviewStatus.REJECTED
        self.resolved_at = datetime.now(timezone.utc)
        self.reviewer = reviewer
        if comment_text:
            self.comments.append(Comment(text=comment_text, action='reject', reviewer=reviewer))

    def partial_revision(self, reviewer: str = '', comment_text: str = '') -> None:
        self.status = ReviewStatus.PARTIAL_REVISION
        self.resolved_at = datetime.now(timezone.utc)
        self.reviewer = reviewer
        if comment_text:
            self.comments.append(Comment(text=comment_text, action='request_change', reviewer=reviewer))

    def add_comment(self, text: str, reviewer: str = '') -> Comment:
        c = Comment(text=text, action='comment', reviewer=reviewer)
        self.comments.append(c)
        return c
