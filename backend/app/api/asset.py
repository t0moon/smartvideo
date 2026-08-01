from __future__ import annotations

from pathlib import Path

from fastapi import APIRouter, HTTPException, UploadFile, File, Form
from pydantic import BaseModel

from app.config import UPLOAD_DIR, UPLOAD_MAX_SIZE_MB, UPLOAD_ALLOWED_EXT
from assets.service import AssetService
from shared.schemas import Asset, AssetType

router = APIRouter()
svc = AssetService()

# Front-facing upload category -> internal AssetType.
_UPLOAD_TYPE_MAP = {
    'image': AssetType.IMAGE,        # 产品图 / 素材图
    'character': AssetType.CHARACTER,  # 模特图
    'voice': AssetType.VOICE,        # 模特音色
    'bgm': AssetType.BGM,            # 配乐
}


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


@router.post('/upload', response_model=Asset, status_code=201)
async def upload_asset(
    project_id: str = Form(...),
    asset_type: str = Form(...),
    name: str = Form(''),
    file: UploadFile = File(...),
) -> Asset:
    """需求三: 用户上传广告素材（产品图 / 模特图 / 模特音色 / BGM）。

    - 按 ``asset_type`` 校验扩展名白名单（UPLOAD_ALLOWED_EXT）
    - 按 UPLOAD_MAX_SIZE_MB 校验文件大小
    - 落盘到 UPLOAD_DIR，并登记为对应类型的 Asset，供后续合成引用
    """
    if asset_type not in _UPLOAD_TYPE_MAP:
        raise HTTPException(400, f'Unknown asset_type: {asset_type}. '
                                 f'Allowed: {", ".join(_UPLOAD_TYPE_MAP)}')

    allowed = UPLOAD_ALLOWED_EXT[asset_type]
    ext = Path(file.filename or '').suffix.lower()
    if ext not in allowed:
        raise HTTPException(415, f'File type {ext} not allowed for "{asset_type}". '
                                 f'Allowed: {sorted(allowed)}')

    raw = await file.read()
    max_bytes = UPLOAD_MAX_SIZE_MB * 1024 * 1024
    if len(raw) > max_bytes:
        raise HTTPException(413, f'File too large: {len(raw)} bytes '
                                 f'(limit {max_bytes} bytes / {UPLOAD_MAX_SIZE_MB}MB)')

    import uuid
    safe_name = (file.filename or 'upload').strip() or 'upload'
    stored_name = f'{uuid.uuid4().hex[:12]}_{safe_name}'
    dest = UPLOAD_DIR / stored_name
    dest.write_bytes(raw)

    asset = svc.create_asset(
        project_id=project_id,
        asset_type=_UPLOAD_TYPE_MAP[asset_type],
        name=name or safe_name,
        description=f'User upload ({asset_type}): {safe_name}',
        file_path=str(dest),
        tags=[asset_type, 'user_upload'],
        metadata={'uploaded': True, 'original_filename': safe_name, 'size_bytes': len(raw)},
    )
    return asset

