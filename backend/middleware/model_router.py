from __future__ import annotations

from middleware.base import AgentMiddleware
from context.schemas import StageContext, StageOutput


class ModelRouterMiddleware(AgentMiddleware):
    name = 'model_router'

    _STAGE_MODEL_MAP = {
        'requirement': 'gpt-4o-mini',
        'storyboard': 'gpt-4o',
        'scene_gen': 'gpt-4o',
        'video_gen': None,  # Uses video provider
        'stitch': None,     # Uses ffmpeg
    }

    async def before_stage(self, ctx: StageContext) -> StageContext:
        model = self._STAGE_MODEL_MAP.get(ctx.stage_id, 'gpt-4o-mini')
        ctx.provider_outputs['model_router'] = {
            'selected_model': model,
            'stage_id': ctx.stage_id,
        }
        if 'model_override' in ctx.config:
            ctx.provider_outputs['model_router']['model_override'] = ctx.config['model_override']
        return ctx
