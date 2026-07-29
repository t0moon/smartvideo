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
