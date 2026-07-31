from __future__ import annotations

from pydantic import BaseModel


from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from storage.database import get_db
from storage.mysql.models import ReviewModel
from shared.schemas import ReviewTask, ProjectStage, ReviewDecision
from review.service import ReviewService
from review.comment import ReviewStatus

router = APIRouter()
svc = ReviewService()


@router.get('/', response_model=list[ReviewTask])
async def list_reviews(project_id: str | None = None, status: str | None = None) -> list[ReviewTask]:
    records = svc.list_reviews(project_id, status)
    return [_record_to_task(r) for r in records]


@router.get('/{review_id}', response_model=ReviewTask)
async def get_review(review_id: str) -> ReviewTask:
    r = svc.get_review(review_id)
    if not r:
        raise HTTPException(404, 'Review not found')
    return _record_to_task(r)


class ReviewAction(BaseModel):
    reviewer: str = ''
    comment: str = ''


class PartialRevisionBody(ReviewAction):
    revisions: dict | None = None


@router.post('/{review_id}/approve', response_model=ReviewTask)
async def approve_review(review_id: str, body: ReviewAction) -> ReviewTask:
    r = svc.approve(review_id, body.reviewer, body.comment)
    if not r:
        raise HTTPException(404, 'Review not found')
    # Trigger resume
    from runtime.workflow import WorkflowRuntime
    runtime = WorkflowRuntime()
    runtime.resume(r.project_id, review_id)
    return _record_to_task(r)


@router.post('/{review_id}/reject', response_model=ReviewTask)
async def reject_review(review_id: str, body: ReviewAction) -> ReviewTask:
    r = svc.reject(review_id, body.reviewer, body.comment)
    if not r:
        raise HTTPException(404, 'Review not found')
    from runtime.workflow import WorkflowRuntime
    runtime = WorkflowRuntime()
    runtime.resume(r.project_id, review_id)
    return _record_to_task(r)


@router.post('/{review_id}/partial', response_model=ReviewTask)
async def partial_revision(review_id: str, body: PartialRevisionBody) -> ReviewTask:
    r = svc.partial_revision(review_id, body.reviewer, body.comment)
    if not r:
        raise HTTPException(404, 'Review not found')
    return _record_to_task(r)


@router.post('/{review_id}/comment', response_model=ReviewTask)
async def add_comment(review_id: str, body: ReviewAction) -> ReviewTask:
    r = svc.add_comment(review_id, body.comment, body.reviewer)
    if not r:
        raise HTTPException(404, 'Review not found')
    return _record_to_task(r)


from pydantic import BaseModel


def _record_to_task(r) -> ReviewTask:
    return ReviewTask(
        review_id=r.review_id,
        project_id=r.project_id,
        stage=r.stage,
        status=ReviewDecision(r.status.value) if hasattr(r.status, 'value') else ReviewDecision.PENDING,
        content=r.content,
        comments=[{'text': c.text, 'action': c.action, 'reviewer': c.reviewer, 'created_at': str(c.created_at)} for c in r.comments],
        created_at=r.created_at,
        resolved_at=r.resolved_at,
        reviewer=r.reviewer,
    )


