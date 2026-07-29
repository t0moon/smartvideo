from __future__ import annotations

from typing import Any

from shared.schemas import Asset, AssetType
from assets.repository import AssetRepository


class AssetService:
    def __init__(self, repo: AssetRepository | None = None) -> None:
        self.repo = repo or AssetRepository()

    def create_asset(
        self,
        project_id: str,
        asset_type: AssetType,
        name: str,
        description: str = '',
        file_path: str = '',
        tags: list[str] | None = None,
        metadata: dict[str, Any] | None = None,
    ) -> Asset:
        import uuid
        asset = Asset(
            asset_id=f'asset_{uuid.uuid4().hex[:12]}',
            project_id=project_id,
            asset_type=asset_type,
            name=name,
            description=description,
            file_path=file_path,
            tags=tags or [],
            metadata=metadata or {},
        )
        self.repo.save(asset)
        return asset

    def create_brand_asset(self, project_id: str, brand_data: dict[str, Any]) -> Asset:
        return self.create_asset(
            project_id=project_id,
            asset_type=AssetType.BRAND,
            name=brand_data.get('brand_name', brand_data.get('product_name', 'Unknown Brand')),
            description=brand_data.get('product_description', ''),
            tags=[brand_data.get('industry', ''), 'brand'],
            metadata=brand_data,
        )

    def create_prompt_asset(self, project_id: str, prompt: str, scene_title: str = '') -> Asset:
        return self.create_asset(
            project_id=project_id,
            asset_type=AssetType.PROMPT,
            name=f'Prompt: {scene_title or prompt[:50]}',
            description=prompt,
            tags=['prompt', scene_title],
            metadata={'prompt': prompt, 'scene_title': scene_title},
        )

    def create_media_asset(self, project_id: str, file_path: str, name: str) -> Asset:
        return self.create_asset(
            project_id=project_id,
            asset_type=AssetType.VIDEO,
            name=name,
            file_path=file_path,
            tags=['video', 'generated'],
        )

    def get_asset(self, asset_id: str) -> Asset | None:
        return self.repo.get(asset_id)

    def list_assets(self, asset_type: AssetType | None = None, project_id: str | None = None) -> list[Asset]:
        return self.repo.list_by_type(asset_type=asset_type, project_id=project_id)

    def delete_asset(self, asset_id: str) -> bool:
        return self.repo.delete(asset_id)

    def search_assets(self, query: str) -> list[Asset]:
        return self.repo.search_by_tag(query)

    def collect_project_assets(self, project_id: str, artifacts: dict[str, Any]) -> list[Asset]:
        created: list[Asset] = []
        # Brand profile -> Brand asset
        if 'brand_profile' in artifacts:
            a = self.create_brand_asset(project_id, artifacts['brand_profile'])
            created.append(a)
        # Storyboard prompts -> Prompt assets
        if 'storyboard' in artifacts:
            sb = artifacts['storyboard']
            if 'scenes' in sb:
                for scene in sb['scenes']:
                    prompt = scene.get('prompt', '')
                    if prompt:
                        a = self.create_prompt_asset(project_id, prompt, scene.get('title', ''))
                        created.append(a)
        # Generated clips -> Media assets
        if 'clips' in artifacts:
            for scene_id, clip_path in artifacts['clips'].items():
                a = self.create_media_asset(project_id, clip_path, f'Clip: {scene_id}')
                created.append(a)
        return created
