from __future__ import annotations

from fastapi import APIRouter, HTTPException
from pydantic import BaseModel

from project.service import ProjectService
from runtime.workflow import WorkflowRuntime
from review.service import ReviewService

router = APIRouter()
svc = ProjectService()
reviews = ReviewService()


class RunRequest(BaseModel):
    brief: str


class RunResponse(BaseModel):
    project_id: str
    status: str = ''
    final_video_path: str = ''
    pause_review_id: str = ''
    error: str = ''


@router.post('/run/{project_id}')
async def run_pipeline(project_id: str, body: RunRequest) -> RunResponse:
    try:
        project = svc.get_project(project_id)
    except Exception:
        raise HTTPException(404, f'Project not found: {project_id}')

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
async def resume_pipeline(project_id: str, review_id: str) -> RunResponse:
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
