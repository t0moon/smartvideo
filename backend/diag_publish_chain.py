"""Reproduce the EVENT_PIPELINE_PAUSED -> ChannelManager.notify_review chain
without sending a real Feishu card (monkeypatch). Reveals whether the
subscriber fires for an asset_prep-style event."""
import os, sys, time

env_path = os.path.join(os.path.dirname(__file__), ".env")
if os.path.exists(env_path):
    for line in open(env_path, encoding="utf-8"):
        line = line.strip()
        if not line or line.startswith("#") or "=" not in line:
            continue
        k, v = line.split("=", 1)
        os.environ.setdefault(k.strip(), v.strip())

from events.bus import get_event_bus, EVENT_PIPELINE_PAUSED
from channels.feishu import FeishuChannel

# Monkeypatch: record calls, do NOT send real card
calls = []
async def _fake_notify(self, project_id, review_id, stage):
    calls.append((project_id, review_id, stage))
    print(f"[diag] >>> notify_review CALLED for {project_id} / {stage}", flush=True)
    return {"status": "stub"}
FeishuChannel.notify_review = _fake_notify

from channels.manager import get_channel_manager
mgr = get_channel_manager()
mgr.ensure_channel()
mgr.register_subscribers()

bus = get_event_bus()
subs = bus._subscribers.get(EVENT_PIPELINE_PAUSED, [])
print(f"[diag] subscribers for {EVENT_PIPELINE_PAUSED}: {len(subs)}", flush=True)

print("[diag] publishing asset_prep pause event ...", flush=True)
bus.publish(__import__("events.bus", fromlist=["Event"]).Event(EVENT_PIPELINE_PAUSED, {
    "project_id": "proj_35fe6157acab", "review_id": "7a33b6ea932940c1", "stage": "asset_prep"}))

time.sleep(6)
print(f"[diag] notify_review was called {len(calls)} time(s): {calls}", flush=True)
print("[diag] done", flush=True)
