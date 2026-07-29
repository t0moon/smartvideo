"""Channel management: channel selection, lifecycle, event bridging."""
from __future__ import annotations

import threading
from typing import Any

from channels.base import BaseChannel
from channels.feishu import FeishuChannel
from channels.feishu.async_executor import run_async
from channels.webhook import WebhookChannel
from channels.feishu.messages import build_status_card
from events.bus import (
    Event,
    get_event_bus,
    EVENT_PIPELINE_PAUSED,
    EVENT_REVIEW_CREATED,
    EVENT_REVIEW_RESOLVED,
)
from app.config import (
    FEISHU_ENABLED,
    FEISHU_APP_ID,
    FEISHU_APP_SECRET,
    FEISHU_REVIEWER_OPEN_ID,
)


async def _send_notification(
    channel: BaseChannel,
    project_id: str,
    review_id: str,
    stage: str,
) -> None:
    try:
        await channel.notify_review(project_id, review_id, stage)
    except Exception as e:
        print(f"  [Channel] Failed to send notification: {e}")


async def _send_status_card(
    channel: BaseChannel,
    project_id: str,
    stage: str,
    status: str,
    message: str = "",
) -> None:
    """Send a status update card (e.g. review approved/rejected)."""
    try:
        if isinstance(channel, FeishuChannel):
            open_id = channel.reviewer_open_id
            if not open_id:
                return
            card = build_status_card(project_id, stage, status, message)
            client = channel._ensure_client()
            await client.send_card(open_id, card)
        # For other channels, fall back to send_message
        else:
            status_msg = f"[{status.upper()}] {stage}: {message}" if message else f"[{status.upper()}] {stage}"
            await channel.send_message("", status_msg)
    except Exception as e:
        print(f"  [Channel] Failed to send status card: {e}")


def _fire_notification(channel: BaseChannel, project_id: str, review_id: str, stage: str) -> None:
    """Fire-and-forget: run the async call on the shared Feishu executor loop."""
    def _target() -> None:
        try:
            run_async(_send_notification(channel, project_id, review_id, stage))
        except Exception as exc:
            print(f"  [Channel] Failed to send notification: {exc}")
    threading.Thread(target=_target, daemon=True).start()


def _fire_status_card(channel: BaseChannel, project_id: str, stage: str, status: str, message: str = "") -> None:
    """Fire-and-forget status card."""
    def _target() -> None:
        try:
            run_async(_send_status_card(channel, project_id, stage, status, message))
        except Exception as exc:
            print(f"  [Channel] Failed to send status card: {exc}")
    threading.Thread(target=_target, daemon=True).start()


class ChannelManager:
    """Manages IM channel lifecycle and bridges EventBus to channel notifications."""

    def __init__(self) -> None:
        self._channel: BaseChannel | None = None
        self._subscribed = False

    def ensure_channel(self) -> BaseChannel:
        """Get or create the active channel based on configuration."""
        if self._channel is not None:
            return self._channel

        if FEISHU_ENABLED:
            print("  [Channel] Feishu enabled, creating FeishuChannel (reviewer_open_id={})".format(FEISHU_REVIEWER_OPEN_ID or "not set"))
            self._channel = FeishuChannel(
                app_id=FEISHU_APP_ID,
                app_secret=FEISHU_APP_SECRET,
                reviewer_open_id=FEISHU_REVIEWER_OPEN_ID,
            )
        else:
            self._channel = WebhookChannel()
            print("  [Channel] Feishu not configured, falling back to WebhookChannel")

        return self._channel

    def register_subscribers(self) -> None:
        """Register EventBus subscribers to bridge pipeline events to IM notifications."""
        if self._subscribed:
            return
        self._subscribed = True

        bus = get_event_bus()
        channel_ref = self

        def on_pipeline_paused(event: Event) -> None:
            data = event.data
            project_id = data.get("project_id", "")
            review_id = data.get("review_id", "")
            stage = data.get("stage", "")
            if project_id and review_id:
                ch = channel_ref.ensure_channel()
                _fire_notification(ch, project_id, review_id, stage)

        def on_review_created(event: Event) -> None:
            data = event.data
            project_id = data.get("project_id", "")
            review_id = data.get("review_id", "")
            stage = data.get("stage", "")
            if project_id and review_id:
                ch = channel_ref.ensure_channel()
                _fire_notification(ch, project_id, review_id, stage)

        def on_review_resolved(event: Event) -> None:
            data = event.data
            project_id = data.get("project_id", "")
            stage = data.get("stage", "")
            status = data.get("status", "")
            if project_id and status:
                ch = channel_ref.ensure_channel()
                status_msg = f"Review {status}: {stage}"
                _fire_status_card(ch, project_id, stage, status, status_msg)

        bus.subscribe(EVENT_PIPELINE_PAUSED, on_pipeline_paused)
        bus.subscribe(EVENT_REVIEW_CREATED, on_review_created)
        bus.subscribe(EVENT_REVIEW_RESOLVED, on_review_resolved)
        print("  [Channel] EventBus subscribers registered")

    async def shutdown(self) -> None:
        if self._channel is not None and hasattr(self._channel, "close"):
            try:
                await self._channel.close()
            except Exception:
                pass


# Global singleton
_manager: ChannelManager | None = None


def get_channel_manager() -> ChannelManager:
    global _manager
    if _manager is None:
        _manager = ChannelManager()
    return _manager


def get_active_channel() -> BaseChannel:
    return get_channel_manager().ensure_channel()


def init_channel_system() -> None:
    """One-call initialization: create channel + register subscribers."""
    mgr = get_channel_manager()
    mgr.ensure_channel()
    mgr.register_subscribers()
