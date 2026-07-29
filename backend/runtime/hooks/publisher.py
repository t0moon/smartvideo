from __future__ import annotations

from typing import Any

from runtime.hooks.base import PipelineHook
from events.bus import Event, get_event_bus, EVENT_PIPELINE_STARTED, EVENT_PIPELINE_COMPLETED, EVENT_PIPELINE_PAUSED, EVENT_PIPELINE_ERROR


class PublisherHook(PipelineHook):
    name = 'publisher'

    async def after_stage(self, project_id: str, stage_id: str, context: dict[str, Any]) -> None:
        bus = get_event_bus()
        error = context.get('_error')
        event_type = EVENT_PIPELINE_ERROR if error else EVENT_PIPELINE_STARTED
        bus.publish(Event(event_type, {
            'project_id': project_id,
            'stage_id': stage_id,
            'error': error or '',
        }))

    async def after_pipeline(self, project_id: str, context: dict[str, Any]) -> None:
        bus = get_event_bus()
        error = context.get('_error')
        event_type = EVENT_PIPELINE_ERROR if error else EVENT_PIPELINE_COMPLETED
        bus.publish(Event(event_type, {
            'project_id': project_id,
            'error': error or '',
        }))
