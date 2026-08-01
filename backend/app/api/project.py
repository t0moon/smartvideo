from __future__ import annotations

from typing import Any

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from storage.database import get_db
from storage.mysql.models import ProjectModel
from shared.schemas import Project, ProjectCreate, ProjectStage

router = APIRouter()


@router.get('/', response_model=list[Project])
async def list_projects(db: AsyncSession = Depends(get_db)) -> list[Project]:
    result = await db.execute(select(ProjectModel).order_by(ProjectModel.updated_at.desc()))
    rows = result.scalars().all()
    return [_model_to_schema(r) for r in rows]


@router.post('/', response_model=Project, status_code=201)
async def create_project(body: ProjectCreate, db: AsyncSession = Depends(get_db)) -> Project:
    model = ProjectModel(
        name=body.name,
        brief=body.brief,
        workflow_name=body.workflow_name,
        stage=ProjectStage.CREATED.value,
    )
    db.add(model)
    await db.commit()
    await db.refresh(model)
    return _model_to_schema(model)


@router.get('/{project_id}', response_model=Project)
async def get_project(project_id: str, db: AsyncSession = Depends(get_db)) -> Project:
    model = await _get_project_or_404(project_id, db)
    return _model_to_schema(model)


@router.get('/{project_id}/status')
async def get_project_status(project_id: str, db: AsyncSession = Depends(get_db)) -> dict:
    """Return the resumable state of a project's pipeline.

    需求一A (HITL continuity): when a pipeline is interrupted at a node, the
    workflow state is persisted to ``workflow_state.json``. This endpoint lets
    the frontend know whether the project is mid-flight (paused) and which
    review id to resume from, so the user gets an explicit "继续项目" button
    instead of silently losing context.

    Returns:
        {
          project_id, stage, paused, pause_stage,
          pause_review_id, has_state, blocked
        }
    """
    model = await _get_project_or_404(project_id, db)
    from workspace.manager import WorkspaceManager
    wm = WorkspaceManager()
    state_data = wm.read_artifact(project_id, 'default', 'workflow_state.json')
    if not state_data:
        return {
            'project_id': project_id,
            'stage': model.stage,
            'paused': False,
            'pause_stage': '',
            'pause_review_id': '',
            'has_state': False,
            'blocked': False,
        }
    meta = state_data.get('meta', {}) or {}
    return {
        'project_id': project_id,
        'stage': state_data.get('current_stage') or model.stage,
        'paused': bool(state_data.get('paused')),
        'pause_stage': meta.get('pause_stage', ''),
        'pause_review_id': meta.get('pause_review_id', ''),
        'has_state': True,
        'blocked': False,
    }


@router.patch('/{project_id}', response_model=Project)
async def update_project(project_id: str, body: dict[str, Any], db: AsyncSession = Depends(get_db)) -> Project:
    model = await _get_project_or_404(project_id, db)
    for key, value in body.items():
        if key == 'meta':
            model.meta_json = value
        elif key == 'stage':
            model.stage = value
        elif key == 'name':
            model.name = value
        elif key == 'brief':
            model.brief = value
    await db.commit()
    await db.refresh(model)
    return _model_to_schema(model)


@router.delete('/{project_id}', status_code=204)
async def delete_project(project_id: str, db: AsyncSession = Depends(get_db)) -> None:
    model = await _get_project_or_404(project_id, db)
    await db.delete(model)
    await db.commit()


async def _get_project_or_404(project_id: str, db: AsyncSession) -> ProjectModel:
    result = await db.execute(select(ProjectModel).where(ProjectModel.project_id == project_id))
    model = result.scalar_one_or_none()
    if not model:
        raise HTTPException(404, f'Project not found: {project_id}')
    return model


def _model_to_schema(m: ProjectModel) -> Project:
    return Project(
        project_id=m.project_id,
        name=m.name,
        brief=m.brief or '',
        workflow_name=m.workflow_name or 'product_ad',
        stage=ProjectStage(m.stage) if m.stage else ProjectStage.CREATED,
        created_at=m.created_at,
        updated_at=m.updated_at,
        archived_at=m.archived_at,
        meta=m.meta_json or {},
    )
