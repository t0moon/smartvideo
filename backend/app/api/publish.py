from __future__ import annotations

from fastapi import APIRouter, HTTPException
from pydantic import BaseModel

from tools.publish import get_publisher, TikTokPublisher, YouTubePublisher, XiaoHongShuPublisher

router = APIRouter()


class PublishBody(BaseModel):
    video_path: str
    title: str
    description: str = ''
    tags: list[str] = []
    platform: str = 'tiktok'


class PublishResponse(BaseModel):
    status: str
    platform: str
    publish_id: str = ''
    url: str = ''


@router.post('/{project_id}', response_model=PublishResponse)
async def publish_video(project_id: str, body: PublishBody) -> PublishResponse:
    publisher = get_publisher(body.platform)
    result = await publisher.publish(
        video_path=body.video_path,
        title=body.title,
        description=body.description,
        tags=body.tags,
    )
    return PublishResponse(
        status=result.get('status', 'queued'),
        platform=body.platform,
        publish_id=result.get('publish_id', ''),
        url=result.get('url', ''),
    )


@router.get('/status/{publish_id}', response_model=PublishResponse)
async def publish_status(publish_id: str) -> PublishResponse:
    platform = publish_id.split('_')[0] if '_' in publish_id else 'tiktok'
    publisher = get_publisher(platform)
    result = await publisher.check_status(publish_id)
    return PublishResponse(
        status=result.get('status', 'unknown'),
        platform=platform,
        publish_id=publish_id,
    )
