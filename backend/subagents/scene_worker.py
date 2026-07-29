from __future__ import annotations

from typing import Any

from agents.lead_agent import LeadAgent
from shared.schemas import VideoSpec, BrandProfile, Storyboard
from subagents.base import BaseSubagent


class SceneWorkerSubagent(BaseSubagent):
    name = 'scene_worker'

    def __init__(self) -> None:
        self.agent = LeadAgent()

    async def execute(self, task: dict[str, Any], context: dict[str, Any]) -> dict[str, Any]:
        scene_index = task.get('scene_index', 0)
        spec_data = context.get('video_spec', {})
        brand_data = context.get('brand_profile', {})

        spec = VideoSpec.model_validate(spec_data) if spec_data else VideoSpec()
        brand = BrandProfile.model_validate(brand_data) if brand_data else None

        storyboard = self.agent.generate_storyboard(spec, brand)

        if scene_index < len(storyboard.scenes):
            scene = storyboard.scenes[scene_index]
            return {
                'scene_index': scene_index,
                'scene': scene.model_dump(),
                'prompt': scene.prompt,
                'status': 'completed',
            }

        return {
            'scene_index': scene_index,
            'status': 'no_scene',
        }
