"""Tests for Event Bus."""
from __future__ import annotations

from events.bus import EventBus, Event, EventPriority


class TestEventBus:
    def test_publish_and_subscribe(self) -> None:
        bus = EventBus()
        received: list[Event] = []

        def handler(e: Event) -> None:
            received.append(e)

        bus.subscribe("test.event", handler)
        bus.publish(Event("test.event", {"key": "val"}))
        assert len(received) == 1
        assert received[0].event_type == "test.event"
        assert received[0].data["key"] == "val"

    def test_wildcard_subscriber(self) -> None:
        bus = EventBus()
        received: list[Event] = []

        def handler(e: Event) -> None:
            received.append(e)

        bus.subscribe("*", handler)
        bus.publish(Event("a.b"))
        bus.publish(Event("c.d"))
        assert len(received) == 2

    def test_unsubscribe(self) -> None:
        bus = EventBus()

        def handler(e: Event) -> None:
            pass

        bus.subscribe("t", handler)
        bus.unsubscribe("t", handler)
        # No error should occur
        bus.publish(Event("t"))

    def test_history(self) -> None:
        bus = EventBus()
        bus.publish(Event("a"))
        bus.publish(Event("b"))
        bus.publish(Event("a"))
        history = bus.get_history()
        assert len(history) == 3
        filtered = bus.get_history(event_type="a")
        assert len(filtered) == 2

    def test_event_priority(self) -> None:
        e = Event("test", priority=EventPriority.HIGH)
        assert e.priority == EventPriority.HIGH
        assert e.event_id
