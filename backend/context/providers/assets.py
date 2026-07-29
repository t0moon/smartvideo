from __future__ import annotations

from typing import Any

from assets.service import AssetService


class AssetContextProvider:
    name = 'assets'

    def provide(self, project_id: str, run_id: str = 'default') -> dict[str, Any]:
        svc = AssetService()
        assets = svc.list_assets(project_id=project_id)
        return {
            'count': len(assets),
            'assets': [a.model_dump() for a in assets[:20]],
            'brand_assets': [a.model_dump() for a in assets if a.asset_type.value == 'brand'],
            'prompt_assets': [a.model_dump() for a in assets if a.asset_type.value == 'prompt'],
        }
