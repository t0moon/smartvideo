from __future__ import annotations

from typing import Any

from middleware.base import AgentMiddleware
from context.schemas import StageContext, StageOutput
from observability.tracing import get_tracer
from observability.metrics import get_metrics
from observability.logging import get_logger


class TracingMiddleware(AgentMiddleware):
    name = 'tracing'

    async def before_stage(self, ctx: StageContext) -> StageContext:
        tracer = get_tracer()
        span = tracer.start_span(f'stage.{ctx.stage_id}', attributes={
            'project_id': ctx.project_id,
            'stage_id': ctx.stage_id,
            'inputs': list(ctx.inputs.keys()),
        })
        ctx.provider_outputs['_tracing_span_id'] = span.span_id
        ctx.provider_outputs['_tracing_trace_id'] = span.trace_id

        get_logger().info(ctx.project_id, ctx.stage_id,
                          f'Stage started: {ctx.stage_id}',
                          trace_id=span.trace_id,
                          inputs=list(ctx.inputs.keys()))
        return ctx

    async def after_stage(self, ctx: StageContext, output: StageOutput) -> StageOutput:
        tracer = get_tracer()
        metrics = get_metrics()
        logger = get_logger()

        span_id = ctx.provider_outputs.get('_tracing_span_id', '')
        trace_id = ctx.provider_outputs.get('_tracing_trace_id', '')

        # Find and end the span
        if trace_id:
            spans = tracer.get_trace(trace_id)
            for span in spans:
                if span.span_id == span_id:
                    status = 'error' if output.error else 'ok'
                    tracer.end_span(span, status)
                    span.attributes['outputs'] = list(output.outputs.keys())
                    duration = span.duration_ms
                    break

        if output.error:
            metrics.increment('stage.error', {'stage_id': ctx.stage_id})
            logger.error(ctx.project_id, ctx.stage_id,
                         f'Stage failed: {output.error}',
                         trace_id=trace_id,
                         error=output.error)
        else:
            metrics.increment('stage.completed', {'stage_id': ctx.stage_id})
            metrics.timing('stage.duration', duration if 'duration' in dir() else 0,
                            {'stage_id': ctx.stage_id})
            logger.info(ctx.project_id, ctx.stage_id,
                        f'Stage completed: {ctx.stage_id}',
                        trace_id=trace_id,
                        outputs=list(output.outputs.keys()))

        return output
