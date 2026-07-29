from __future__ import annotations

import json
import uuid
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from app.config import ASSETS_DIR
from shared.schemas import Asset, AssetType
from shared.constants import ASSET_INDEX_FILE


class AssetRepository:
    def __init__(self, base_dir: Path | None = None) -> None:
        self.base_dir = base_dir or ASSETS_DIR
        self.base_dir.mkdir(parents=True, exist_ok=True)

    def _asset_path(self, asset_type: str, asset_id: str) -> Path:
        return self.base_dir / asset_type / f'{asset_id}.json'

    def save(self, asset: Asset) -> Path:
        d = self.base_dir / asset.asset_type.value
        d.mkdir(parents=True, exist_ok=True)
        path = d / f'{asset.asset_id}.json'
        path.write_text(asset.model_dump_json(indent=2), encoding='utf-8')
        self._update_index(asset)
        return path

    def get(self, asset_id: str) -> Asset | None:
        for asset_type_dir in self.base_dir.iterdir():
            if asset_type_dir.is_dir():
                f = asset_type_dir / f'{asset_id}.json'
                if f.exists():
                    return Asset.model_validate(json.loads(f.read_text(encoding='utf-8')))
        return None

    def list_by_type(self, asset_type: AssetType | None = None, project_id: str | None = None) -> list[Asset]:
        results: list[Asset] = []
        if asset_type:
            dirs = [self.base_dir / asset_type.value]
        else:
            dirs = [d for d in self.base_dir.iterdir() if d.is_dir()]
        for d in dirs:
            if not d.exists():
                continue
            for f in d.iterdir():
                if f.suffix == '.json':
                    try:
                        a = Asset.model_validate(json.loads(f.read_text(encoding='utf-8')))
                        if project_id and a.project_id != project_id:
                            continue
                        results.append(a)
                    except Exception:
                        continue
        results.sort(key=lambda a: a.created_at, reverse=True)
        return results

    def delete(self, asset_id: str) -> bool:
        for asset_type_dir in self.base_dir.iterdir():
            if asset_type_dir.is_dir():
                f = asset_type_dir / f'{asset_id}.json'
                if f.exists():
                    f.unlink()
                    return True
        return False

    def _update_index(self, asset: Asset) -> None:
        index_path = self.base_dir / ASSET_INDEX_FILE
        index: dict[str, Any] = {}
        if index_path.exists():
            index = json.loads(index_path.read_text(encoding='utf-8'))
        tags = asset.tags + [asset.asset_type.value, asset.name]
        for tag in tags:
            if tag not in index:
                index[tag] = []
            if asset.asset_id not in index[tag]:
                index[tag].append(asset.asset_id)
        index_path.write_text(json.dumps(index, ensure_ascii=False, indent=2), encoding='utf-8')

    def search_by_tag(self, query: str) -> list[Asset]:
        index_path = self.base_dir / ASSET_INDEX_FILE
        if not index_path.exists():
            return []
        index = json.loads(index_path.read_text(encoding='utf-8'))
        q = query.lower()
        matched_ids: set[str] = set()
        for tag, ids in index.items():
            if q in tag.lower():
                matched_ids.update(ids)
        all_assets = self.list_by_type()
        return [a for a in all_assets if a.asset_id in matched_ids]
