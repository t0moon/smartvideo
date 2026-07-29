from __future__ import annotations

from middleware.base import AgentMiddleware
from context.schemas import StageContext, StageOutput
from review.service import ReviewService


class ApprovalMiddleware(AgentMiddleware):
    name = 'approval'

    async def before_stage(self, ctx: StageContext) -> StageContext:
        if ctx.stage_id in ('requirement', 'storyboard', 'video_gen'):
            svc = ReviewService()
            if svc.is_project_blocked(ctx.project_id):
                ctx.provider_outputs['approval'] = {
                    'blocked': True,
                    'message': 'Project has pending reviews',
                }
        return ctx

    async def after_stage(self, ctx: StageContext, output: StageOutput) -> StageOutput:
        if ctx.config.get('pause_for_review', False):
            svc = ReviewService()
            stage_map = {'requirement': 'requirement', 'storyboard': 'storyboard', 'video_gen': 'video_review'}
            review_stage = stage_map.get(ctx.stage_id, ctx.stage_id)
            review = svc.create_review(ctx.project_id, review_stage, output.outputs)
            output.outputs['_pause_review_id'] = review.review_id
            output.outputs['_paused'] = True
        return output
