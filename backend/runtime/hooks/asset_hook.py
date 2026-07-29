from __future__ import annotations

from pathlib import Path
from typing import Any

from runtime.hooks.base import PipelineHook
from assets.service import AssetService


class AssetCollectHook(PipelineHook):
    name = 'collect_assets'

    def __init__(self) -> None:
        self.assets = AssetService()

    async def after_stage(self, project_id: str, stage_id: str, context: dict[str, Any]) -> None:
        pass  # We collect at the end

    async def after_pipeline(self, project_id: str, context: dict[str, Any]) -> None:
        artifacts = {}
        if 'video_spec' in context:
            artifacts['brand_profile'] = context['video_spec']
        if 'storyboard' in context:
            artifacts['storyboard'] = context['storyboard']
        if 'clips' in context:
            artifacts['clips'] = context['clips']
        if artifacts:
            created = self.assets.collect_project_assets(project_id, artifacts)
            print(f'  [AssetHook] Collected {len(created)} assets for project {project_id}')
