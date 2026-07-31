from __future__ import annotations

from contextlib import contextmanager
from datetime import datetime, timezone
from typing import Any

from sqlalchemy import create_engine, select
from sqlalchemy.orm import sessionmaker

from review.comment import Comment, ReviewRecord, ReviewStage, ReviewStatus
from events.bus import Event, get_event_bus, EVENT_REVIEW_RESOLVED
from storage.database import DB_PATH
from storage.mysql.models import ReviewModel

# Sync engine used only for review persistence so reviews survive backend
# restarts (the previous in-memory queue was lost on every restart, which
# left pipelines stuck at their human-in-the-loop pause points).
_sync_engine = create_engine(f'sqlite:///{DB_PATH}', future=True, pool_pre_ping=True)
_SyncSession = sessionmaker(_sync_engine, expire_on_commit=False)


def _model_to_record(m: ReviewModel) -> ReviewRecord:
    comments: list[Comment] = []
    for c in (m.comments or []):
        raw_created = c.get('created_at') if isinstance(c, dict) else None
        created = (
            datetime.fromisoformat(raw_created)
            if isinstance(raw_created, str)
            else (raw_created or datetime.now(timezone.utc))
        )
        comments.append(Comment(
            text=c.get('text', '') if isinstance(c, dict) else '',
            action=c.get('action', 'comment') if isinstance(c, dict) else 'comment',
            reviewer=c.get('reviewer', '') if isinstance(c, dict) else '',
            created_at=created,
        ))
    return ReviewRecord(
        review_id=m.review_id,
        project_id=m.project_id,
        stage=ReviewStage(m.stage),
        status=ReviewStatus(m.status),
        content=m.content or {},
        comments=comments,
        created_at=m.created_at,
        resolved_at=m.resolved_at,
        reviewer=m.reviewer,
    )


def _record_to_model_payload(record: ReviewRecord) -> dict[str, Any]:
    return {
        'status': record.status.value,
        'resolved_at': record.resolved_at,
        'reviewer': record.reviewer,
        'comments': [c.model_dump(mode='json') for c in record.comments],
    }


class ReviewService:
    def __init__(self, queue=None) -> None:
        # `queue` retained for backwards-compatible construction; persistence
        # now lives in SQLite via the sync engine above.
        self.queue = queue

    def _publish_resolved(self, record: ReviewRecord) -> None:
        bus = get_event_bus()
        bus.publish(Event(EVENT_REVIEW_RESOLVED, {
            'project_id': record.project_id,
            'review_id': record.review_id,
            'stage': record.stage.value,
            'status': record.status.value,
            'reviewer': record.reviewer,
        }))

    def _create(self, project_id: str, stage: ReviewStage, content: dict[str, Any]) -> ReviewRecord:
        with _SyncSession() as db:
            m = ReviewModel(project_id=project_id, stage=stage.value, content=content)
            db.add(m)
            db.commit()
            db.refresh(m)
            return _model_to_record(m)

    def create_requirement_review(self, project_id: str, video_spec: dict[str, Any]) -> ReviewRecord:
        return self._create(project_id, ReviewStage.REQUIREMENT, {'type': 'video_spec', 'spec': video_spec})

    def create_storyboard_review(self, project_id: str, storyboard: dict[str, Any]) -> ReviewRecord:
        return self._create(project_id, ReviewStage.STORYBOARD, {'type': 'storyboard', 'storyboard': storyboard})

    def create_asset_review(self, project_id: str, assets: dict[str, Any]) -> ReviewRecord:
        return self._create(project_id, ReviewStage.ASSET_PREP, {'type': 'assets', 'assets': assets})

    def create_video_review(self, project_id: str, video_info: dict[str, Any]) -> ReviewRecord:
        return self._create(project_id, ReviewStage.VIDEO_REVIEW, {'type': 'video', 'video': video_info})

    def _mutate(self, review_id: str, fn) -> ReviewRecord | None:
        with _SyncSession() as db:
            m = db.get(ReviewModel, review_id)
            if not m:
                return None
            record = _model_to_record(m)
            fn(record)
            payload = _record_to_model_payload(record)
            m.status = payload['status']
            m.resolved_at = payload['resolved_at']
            m.reviewer = payload['reviewer']
            m.comments = payload['comments']
            db.commit()
            self._publish_resolved(record)
            return record

    def approve(self, review_id: str, reviewer: str = '', comment: str = '') -> ReviewRecord | None:
        return self._mutate(review_id, lambda r: r.approve(reviewer, comment))

    def reject(self, review_id: str, reviewer: str = '', comment: str = '') -> ReviewRecord | None:
        return self._mutate(review_id, lambda r: r.reject(reviewer, comment))

    def partial_revision(self, review_id: str, reviewer: str = '', comment: str = '') -> ReviewRecord | None:
        return self._mutate(review_id, lambda r: r.partial_revision(reviewer, comment))

    def add_comment(self, review_id: str, text: str, reviewer: str = '') -> ReviewRecord | None:
        with _SyncSession() as db:
            m = db.get(ReviewModel, review_id)
            if not m:
                return None
            record = _model_to_record(m)
            record.add_comment(text, reviewer)
            m.comments = [c.model_dump(mode='json') for c in record.comments]
            db.commit()
            return record

    def get_review(self, review_id: str) -> ReviewRecord | None:
        with _SyncSession() as db:
            m = db.get(ReviewModel, review_id)
            return _model_to_record(m) if m else None

    def list_pending(self, project_id: str | None = None) -> list[ReviewRecord]:
        return self.list_reviews(project_id=project_id, status=ReviewStatus.PENDING.value)

    def list_by_project(self, project_id: str) -> list[ReviewRecord]:
        return self.list_reviews(project_id=project_id)

    def list_reviews(self, project_id: str | None = None, status: str | None = None) -> list[ReviewRecord]:
        with _SyncSession() as db:
            q = select(ReviewModel)
            if project_id:
                q = q.where(ReviewModel.project_id == project_id)
            if status:
                q = q.where(ReviewModel.status == status)
            rows = db.execute(q).scalars().all()
            return [_model_to_record(r) for r in rows]

    def is_project_blocked(self, project_id: str) -> bool:
        return any(r.status == ReviewStatus.PENDING for r in self.list_reviews(project_id=project_id))
