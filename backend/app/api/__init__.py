from __future__ import annotations

from fastapi import APIRouter

from . import project, workspace, review, webhook, asset, publish, observability
from ..websocket import router as ws_router

router = APIRouter()
router.include_router(project.router, prefix='/projects', tags=['Projects'])
router.include_router(workspace.router, prefix='/workspace', tags=['Workspace'])
router.include_router(review.router, prefix='/reviews', tags=['Reviews'])
router.include_router(webhook.router, prefix='/webhooks', tags=['Webhooks'])
router.include_router(asset.router, prefix='/assets', tags=['Assets'])
router.include_router(publish.router, prefix='/publish', tags=['Publish'])
router.include_router(observability.router)
router.include_router(ws_router)


@router.get('/health')
async def health():
    return {'status': 'ok', 'version': '0.2.0'}
