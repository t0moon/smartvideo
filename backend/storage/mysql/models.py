from __future__ import annotations

import uuid
from datetime import datetime, timezone

from sqlalchemy import Column, String, Text, Integer, Boolean, DateTime, JSON, ForeignKey
from sqlalchemy.orm import relationship

from storage.database import Base


def _utcnow() -> datetime:
    return datetime.now(timezone.utc)


def _new_id() -> str:
    return uuid.uuid4().hex[:16]


class ProjectModel(Base):
    __tablename__ = 'projects'

    project_id = Column(String(32), primary_key=True, default=_new_id)
    name = Column(String(200), nullable=False)
    brief = Column(Text, default='')
    workflow_name = Column(String(64), default='product_ad')
    stage = Column(String(32), default='created')
    meta_json = Column('meta', JSON, default=dict)
    created_at = Column(DateTime, default=_utcnow)
    updated_at = Column(DateTime, default=_utcnow, onupdate=_utcnow)
    archived_at = Column(DateTime, nullable=True)

    runs = relationship('RunModel', back_populates='project', cascade='all, delete-orphan')
    assets = relationship('AssetModel', back_populates='project', cascade='all, delete-orphan')
    reviews = relationship('ReviewModel', back_populates='project', cascade='all, delete-orphan')


class RunModel(Base):
    __tablename__ = 'runs'

    run_id = Column(String(32), primary_key=True, default=_new_id)
    project_id = Column(String(32), ForeignKey('projects.project_id'), nullable=False)
    status = Column(String(32), default='pending')
    final_video_path = Column(String(500), default='')
    errors = Column(JSON, default=list)
    started_at = Column(DateTime, default=_utcnow)
    completed_at = Column(DateTime, nullable=True)

    project = relationship('ProjectModel', back_populates='runs')


class AssetModel(Base):
    __tablename__ = 'assets'

    asset_id = Column(String(32), primary_key=True, default=_new_id)
    project_id = Column(String(32), ForeignKey('projects.project_id'), nullable=False)
    asset_type = Column(String(32), nullable=False)
    name = Column(String(200), default='')
    description = Column(Text, default='')
    file_path = Column(String(500), default='')
    tags = Column(JSON, default=list)
    metadata_json = Column('metadata', JSON, default=dict)
    created_at = Column(DateTime, default=_utcnow)

    project = relationship('ProjectModel', back_populates='assets')


class ReviewModel(Base):
    __tablename__ = 'reviews'

    review_id = Column(String(32), primary_key=True, default=_new_id)
    project_id = Column(String(32), ForeignKey('projects.project_id'), nullable=False)
    stage = Column(String(32), nullable=False)
    status = Column(String(32), default='pending')
    content = Column(JSON, default=dict)
    comments = Column(JSON, default=list)
    created_at = Column(DateTime, default=_utcnow)
    resolved_at = Column(DateTime, nullable=True)
    reviewer = Column(String(100), default='')

    project = relationship('ProjectModel', back_populates='reviews')
