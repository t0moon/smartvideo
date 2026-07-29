from __future__ import annotations

import time
from typing import Any

from observability.tracing import get_tracer, TraceSpan
from observability.metrics import get_metrics
from observability.logging import get_logger
from shared.schemas import WorkflowState


def instrument_pipeline_run(project_id: str, brief: str) -> TraceSpan:
    """Create a root span for a full pipeline run."""
    tracer = get_tracer()
    span = tracer.start_span(f'pipeline.run.{project_id}', attributes={
        'project_id': project_id,
        'brief_len': len(brief),
        'phase': 'full_pipeline',
    })
    get_logger().info(project_id, 'pipeline', 'Pipeline started', trace_id=span.trace_id)
    return span


def instrument_pipeline_stage(project_id: str, stage_name: str, parent_span: TraceSpan | None = None) -> TraceSpan:
    """Create a span for a single pipeline stage."""
    tracer = get_tracer()
    span = tracer.start_span(f'stage.{stage_name}.{project_id}', attributes={
        'project_id': project_id,
        'stage': stage_name,
    }, parent_span=parent_span)
    return span


def instrument_pipeline_resume(project_id: str, review_id: str, stage: str) -> TraceSpan:
    """Create a span when a pipeline resumes after review."""
    tracer = get_tracer()
    span = tracer.start_span(f'pipeline.resume.{project_id}', attributes={
        'project_id': project_id,
        'review_id': review_id,
        'stage': stage,
    })
    get_logger().info(project_id, 'pipeline', f'Pipeline resumed at stage: {stage}',
                      trace_id=span.trace_id)
    return span


def instrument_video_generation(project_id: str, scene_id: str, scene_index: int) -> TraceSpan:
    """Create a span for a single video clip generation."""
    tracer = get_tracer()
    return tracer.start_span(f'video.gen.{scene_id}', attributes={
        'project_id': project_id,
        'scene_index': scene_index,
        'scene_id': scene_id,
    })


def record_pipeline_metrics(project_id: str, state: WorkflowState | None, duration_ms: float,
                            success: bool) -> None:
    """Record pipeline-level metrics."""
    metrics = get_metrics()
    metrics.timing('pipeline.total_duration', duration_ms, {'project_id': project_id})
    if success:
        metrics.increment('pipeline.completed', {'project_id': project_id})
    else:
        metrics.increment('pipeline.error', {'project_id': project_id})

    if state and state.errors:
        metrics.gauge('pipeline.error_count', len(state.errors), {'project_id': project_id})

    # Record token and cost from state
    if state:
        total_clips = len(state.clips) if state.clips else 0
        metrics.gauge('pipeline.clip_count', total_clips, {'project_id': project_id})
