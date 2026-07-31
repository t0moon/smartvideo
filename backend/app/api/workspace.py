from __future__ import annotations

from fastapi import APIRouter, HTTPException, Depends
from pydantic import BaseModel
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from project.service import ProjectService
from runtime.workflow import WorkflowRuntime
from review.service import ReviewService
from shared.exceptions import ProjectNotFoundError
from shared.schemas import Project, ProjectStage
from storage.database import get_db
from storage.mysql.models import ProjectModel

router = APIRouter()
svc = ProjectService()
reviews = ReviewService()


async def _ensure_fs_project(project_id: str, db: AsyncSession) -> Project:
    """Return filesystem project; if missing but present in DB, sync it."""
    try:
        return svc.get_project(project_id)
    except ProjectNotFoundError:
        pass

    # Project not in filesystem repo; try to sync from SQL DB.
    result = await db.execute(select(ProjectModel).where(ProjectModel.project_id == project_id))
    model = result.scalar_one_or_none()
    if not model:
        raise HTTPException(404, f'Project not found: {project_id}')

    project = Project(
        project_id=model.project_id,
        name=model.name,
        brief=model.brief or '',
        workflow_name=model.workflow_name or 'product_ad',
        stage=ProjectStage(model.stage) if model.stage else ProjectStage.CREATED,
        created_at=model.created_at,
        updated_at=model.updated_at,
        archived_at=model.archived_at,
        meta=model.meta_json or {},
    )
    svc.repo._save(project)
    return project


class RunRequest(BaseModel):
    brief: str


class RunResponse(BaseModel):
    project_id: str
    status: str = ''
    final_video_path: str = ''
    pause_review_id: str = ''
    error: str = ''


@router.post('/run/{project_id}')
async def run_pipeline(project_id: str, body: RunRequest, db: AsyncSession = Depends(get_db)) -> RunResponse:
    await _ensure_fs_project(project_id, db)

    # Check if blocked by pending review
    if reviews.is_project_blocked(project_id):
        return RunResponse(
            project_id=project_id,
            status='blocked',
            error='Project has pending reviews that must be resolved first',
        )

    runtime = WorkflowRuntime()
    result = runtime.run_pipeline(project_id, body.brief)

    if result.startswith('__PAUSED__:'):
        review_id = result.split(':')[1]
        return RunResponse(
            project_id=project_id,
            status='paused',
            pause_review_id=review_id,
            final_video_path='',
        )

    if result:
        return RunResponse(project_id=project_id, status='completed', final_video_path=result)
    else:
        return RunResponse(project_id=project_id, status='error', error='Pipeline completed with errors')


@router.post('/resume/{project_id}')
async def resume_pipeline(project_id: str, review_id: str, db: AsyncSession = Depends(get_db)) -> RunResponse:
    await _ensure_fs_project(project_id, db)
    runtime = WorkflowRuntime()
    try:
        result = runtime.resume(project_id, review_id)
        if result:
            return RunResponse(project_id=project_id, status='completed', final_video_path=result)
        else:
            # Check if paused again
            state = runtime._load_state(project_id)
            if state.paused:
                pause_id = state.meta.get('pause_review_id', '')
                return RunResponse(project_id=project_id, status='paused', pause_review_id=pause_id)
            return RunResponse(project_id=project_id, status='error', error='Resume completed with errors')
    except Exception as e:
        return RunResponse(project_id=project_id, status='error', error=str(e))
