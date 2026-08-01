from __future__ import annotations

import traceback
import uuid
from datetime import datetime, timezone
from enum import Enum
from typing import Any, Callable


class EventPriority(str, Enum):
    LOW = 'low'
    NORMAL = 'normal'
    HIGH = 'high'


class Event:
    def __init__(
        self,
        event_type: str,
        data: dict[str, Any] | None = None,
        priority: EventPriority = EventPriority.NORMAL,
        source: str = '',
    ) -> None:
        self.event_id: str = uuid.uuid4().hex[:12]
        self.event_type: str = event_type
        self.data: dict[str, Any] = data or {}
        self.priority: EventPriority = priority
        self.source: str = source
        self.created_at: datetime = datetime.now(timezone.utc)


EventHandler = Callable[[Event], None]


class EventBus:
    def __init__(self) -> None:
        self._subscribers: dict[str, list[EventHandler]] = {}
        self._history: list[Event] = []

    def subscribe(self, event_type: str, handler: EventHandler) -> None:
        if event_type not in self._subscribers:
            self._subscribers[event_type] = []
        self._subscribers[event_type].append(handler)

    def unsubscribe(self, event_type: str, handler: EventHandler) -> None:
        if event_type in self._subscribers:
            self._subscribers[event_type] = [h for h in self._subscribers[event_type] if h is not handler]

    def publish(self, event: Event) -> None:
        self._history.append(event)

        # Publish to specific type subscribers
        for handler in self._subscribers.get(event.event_type, []):
            try:
                handler(event)
            except Exception:
                # A failing subscriber must NOT silently break the chain nor
                # swallow the real error ¡X surface it with a full traceback so
                # pipeline-pause notification bugs (e.g. a missing Feishu card)
                # are diagnosable instead of looking like "no reaction".
                print(f"  [EventBus] subscriber error for {event.event_type}:")
                traceback.print_exc()
        # Publish to wildcard subscribers
        for handler in self._subscribers.get('*', []):
            try:
                handler(event)
            except Exception:
                print("  [EventBus] wildcard subscriber error:")
                traceback.print_exc()

    def get_history(self, event_type: str | None = None, limit: int = 50) -> list[Event]:
        events = self._history
        if event_type:
            events = [e for e in events if e.event_type == event_type]
        return events[-limit:]


_bus = EventBus()


def get_event_bus() -> EventBus:
    return _bus


# ©¤©¤ Event Type Constants ©¤©¤©¤©¤©¤©¤©¤©¤©¤©¤©¤©¤©¤©¤©¤©¤©¤©¤©¤©¤©¤©¤©¤©¤©¤©¤©¤©¤©¤©¤
EVENT_PROJECT_CREATED = 'project.created'
EVENT_PROJECT_UPDATED = 'project.updated'
EVENT_PROJECT_DELETED = 'project.deleted'
EVENT_PIPELINE_STARTED = 'pipeline.started'
EVENT_PIPELINE_COMPLETED = 'pipeline.completed'
EVENT_PIPELINE_PAUSED = 'pipeline.paused'
EVENT_PIPELINE_ERROR = 'pipeline.error'
EVENT_REVIEW_CREATED = 'review.created'
EVENT_REVIEW_RESOLVED = 'review.resolved'
EVENT_ASSET_CREATED = 'asset.created'
EVENT_GUARDRAIL_VIOLATION = 'guardrail.violation'
