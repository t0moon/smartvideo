from __future__ import annotations

from typing import Any

from project.service import ProjectService
from workspace.manager import WorkspaceManager
from context.schemas import StageContext, StageOutput
from context.selector import ContextSelector
from middleware.registry import get_registry


class ContextBuilder:
    def __init__(self) -> None:
        self.projects = ProjectService()
        self.workspace = WorkspaceManager()
        self.selector = ContextSelector()
        self.middleware = get_registry()

    def build(self, project_id: str, stage_id: str, run_id: str = 'default') -> StageContext:
        project = self.projects.get_project(project_id)
        config = self.selector.get_stage_config(stage_id)
        required_inputs = config.get('inputs', [])
        provider_names = config.get('providers', [])

        inputs = self._gather_inputs(project_id, run_id, required_inputs)
        provider_outputs = self._run_providers(provider_names, project_id, run_id)

        ctx = StageContext(
            stage_id=stage_id,
            project_id=project_id,
            project=project.model_dump(),
            inputs=inputs,
            assets=provider_outputs.get('assets', {}).get('assets', []),
            reviews=provider_outputs.get('review', {}).get('pending_reviews', []),
            config=config,
            provider_outputs=provider_outputs,
        )
        return ctx

    async def run_stage(self, project_id: str, stage_id: str, brief: str = '', run_id: str = 'default') -> StageOutput:
        ctx = self.build(project_id, stage_id, run_id)
        ctx = await self.middleware.run_before(ctx)

        from agents.lead_agent import LeadAgent
        agent = LeadAgent()
        from shared.schemas import VideoSpec

        outputs: dict[str, Any] = {}
        if stage_id == 'requirement':
            spec = agent.understand_requirement(brief or ctx.project.get('brief', ''))
            outputs['video_spec'] = spec.model_dump()
        elif stage_id == 'storyboard':
            spec_data = ctx.inputs.get('video_spec')
            spec = VideoSpec.model_validate(spec_data) if spec_data else VideoSpec()
            from shared.schemas import BrandProfile
            brand = BrandProfile(brand_name=spec.brand)
            sb = agent.generate_storyboard(spec, brand)
            outputs['storyboard'] = sb.model_dump()
        elif stage_id == 'scene_gen':
            sb_data = ctx.inputs.get('storyboard')
            from shared.schemas import Storyboard
            sb = Storyboard.model_validate(sb_data) if sb_data else Storyboard()
            scenes = agent.generate_scenes(sb)
            outputs['scenes'] = [s.model_dump() for s in scenes]

        out = self.save_output(project_id, stage_id, outputs, run_id)
        out = await self.middleware.run_after(ctx, out)
        return out

    def save_output(self, project_id: str, stage_id: str, outputs: dict[str, Any], run_id: str = 'default') -> StageOutput:
        config = self.selector.get_stage_config(stage_id)
        produced = config.get('produces', [])

        st_out = StageOutput(
            stage_id=stage_id,
            project_id=project_id,
            outputs={k: outputs.get(k) for k in produced if k in outputs},
        )

        for key in produced:
            if key in outputs:
                filename = f'{stage_id}_{key}.json'
                self.workspace.write_artifact(project_id, run_id, filename, outputs[key])

        return st_out

    def _gather_inputs(self, project_id: str, run_id: str, required: list[str]) -> dict[str, Any]:
        gathered = {}
        for name in required:
            data = self.workspace.read_artifact(project_id, run_id, f'{name}.json')
            gathered[name] = data
        return gathered

    def _run_providers(self, provider_names: list[str], project_id: str, run_id: str) -> dict[str, Any]:
        results = {}
        for name in provider_names:
            provider = self.selector.get_provider(name)
            if provider:
                results[name] = provider.provide(project_id, run_id)
        return results
