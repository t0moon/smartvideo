from __future__ import annotations

from middleware.base import AgentMiddleware
from context.schemas import StageContext, StageOutput


class ToolGuardMiddleware(AgentMiddleware):
    name = 'tool_guard'

    _ALLOWED_TOOLS = {'llm_chat', 'video_generate', 'tts_synthesize', 'ffmpeg_stitch', 'asset_search'}

    async def before_stage(self, ctx: StageContext) -> StageContext:
        requested = ctx.config.get('tools', [])
        blocked = [t for t in requested if t not in self._ALLOWED_TOOLS]
        if blocked:
            ctx.provider_outputs['tool_guard'] = {
                'blocked_tools': blocked,
                'message': f'Blocked tools: {blocked}',
            }
        return ctx
