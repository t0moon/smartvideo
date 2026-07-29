from __future__ import annotations

from typing import Any

from events.bus import (
    get_event_bus, Event,
    EVENT_PIPELINE_STARTED, EVENT_PIPELINE_COMPLETED,
    EVENT_PIPELINE_PAUSED, EVENT_PIPELINE_ERROR,
    EVENT_PROJECT_CREATED, EVENT_PROJECT_UPDATED,
    EVENT_REVIEW_CREATED, EVENT_REVIEW_RESOLVED,
    EVENT_ASSET_CREATED, EVENT_GUARDRAIL_VIOLATION,
)
from observability.tracing import get_tracer
from observability.logging import get_logger
from observability.metrics import get_metrics


def _make_span_from_event(event: Event, span_name: str) -> None:
    """Create a span from an event bus event."""
    tracer = get_tracer()
    span = tracer.start_span(span_name, attributes={
        'event_type': event.event_type,
        'event_id': event.event_id,
        'source': event.source,
        **event.data,
    })
    tracer.end_span(span, 'ok')


def _on_pipeline_started(event: Event) -> None:
    _make_span_from_event(event, f'pipeline.start.{event.data.get("project_id", "?")}')
    get_logger().info(
        event.data.get('project_id', ''),
        'pipeline',
        f'Pipeline started',
        extra_data=event.data,
    )
    get_metrics().increment('pipeline.started')


def _on_pipeline_completed(event: Event) -> None:
    pid = event.data.get('project_id', '?')
    _make_span_from_event(event, f'pipeline.complete.{pid}')
    get_logger().info(pid, 'pipeline', 'Pipeline completed')
    get_metrics().increment('pipeline.completed')


def _on_pipeline_paused(event: Event) -> None:
    pid = event.data.get('project_id', '?')
    _make_span_from_event(event, f'pipeline.pause.{pid}')
    stage = event.data.get('stage', '?')
    get_logger().info(pid, 'pipeline', f'Pipeline paused at stage: {stage}')
    get_metrics().increment('pipeline.paused', {'stage': stage})


def _on_pipeline_error(event: Event) -> None:
    pid = event.data.get('project_id', '?')
    _make_span_from_event(event, f'pipeline.error.{pid}')
    get_logger().error(pid, 'pipeline', 'Pipeline error', error=event.data.get('error', ''))
    get_metrics().increment('pipeline.error')


def _on_project_created(event: Event) -> None:
    get_metrics().increment('project.created')
    get_logger().info(event.data.get('project_id', ''), 'project', 'Project created')


def _on_review_created(event: Event) -> None:
    pid = event.data.get('project_id', '?')
    get_logger().info(pid, 'review', f'Review created')
    get_metrics().increment('review.created')


def _on_review_resolved(event: Event) -> None:
    get_metrics().increment('review.resolved')


def _on_guardrail_violation(event: Event) -> None:
    get_metrics().increment('guardrail.violation')
    get_logger().warning(
        event.data.get('project_id', ''),
        'guardrail',
        'Guardrail violation',
        extra_data=event.data,
    )


def register_observability_subscribers() -> None:
    """Subscribe all observability handlers to the event bus."""
    bus = get_event_bus()
    bus.subscribe(EVENT_PIPELINE_STARTED, _on_pipeline_started)
    bus.subscribe(EVENT_PIPELINE_COMPLETED, _on_pipeline_completed)
    bus.subscribe(EVENT_PIPELINE_PAUSED, _on_pipeline_paused)
    bus.subscribe(EVENT_PIPELINE_ERROR, _on_pipeline_error)
    bus.subscribe(EVENT_PROJECT_CREATED, _on_project_created)
    bus.subscribe(EVENT_REVIEW_CREATED, _on_review_created)
    bus.subscribe(EVENT_REVIEW_RESOLVED, _on_review_resolved)
    bus.subscribe(EVENT_GUARDRAIL_VIOLATION, _on_guardrail_violation)
