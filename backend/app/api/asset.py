from __future__ import annotations

from fastapi import APIRouter, HTTPException
from pydantic import BaseModel

from assets.service import AssetService
from shared.schemas import Asset, AssetType

router = APIRouter()
svc = AssetService()


class AssetCreateBody(BaseModel):
    project_id: str
    asset_type: str
    name: str
    description: str = ''
    file_path: str = ''
    tags: list[str] = []


@router.get('/', response_model=list[Asset])
async def list_assets(asset_type: str | None = None, project_id: str | None = None) -> list[Asset]:
    at = AssetType(asset_type) if asset_type else None
    return svc.list_assets(asset_type=at, project_id=project_id)


@router.get('/search', response_model=list[Asset])
async def search_assets(q: str = '') -> list[Asset]:
    if not q:
        return []
    return svc.search_assets(q)


@router.get('/{asset_id}', response_model=Asset)
async def get_asset(asset_id: str) -> Asset:
    a = svc.get_asset(asset_id)
    if not a:
        raise HTTPException(404, 'Asset not found')
    return a


@router.post('/', response_model=Asset, status_code=201)
async def create_asset(body: AssetCreateBody) -> Asset:
    return svc.create_asset(
        project_id=body.project_id,
        asset_type=AssetType(body.asset_type),
        name=body.name,
        description=body.description,
        file_path=body.file_path,
        tags=body.tags,
    )


@router.delete('/{asset_id}', status_code=204)
async def delete_asset(asset_id: str) -> None:
    if not svc.delete_asset(asset_id):
        raise HTTPException(404, 'Asset not found')
