"""Shared async executor for Feishu client calls.

Both the WebSocket listener and the ChannelManager bridge need to call
FeishuClient coroutines. Running ``asyncio.run()`` from workflow threads
repeatedly creates/destroys event loops and eventually raises
``Event loop is closed`` because the cached ``httpx.AsyncClient`` is bound to
a closed loop.

This module keeps one global event loop running in a daemon thread and
schedules all FeishuClient coroutines onto it via
``asyncio.run_coroutine_threadsafe``.
"""
from __future__ import annotations

import asyncio
import threading
from typing import Any

_executor_thread: threading.Thread | None = None
_loop: asyncio.AbstractEventLoop | None = None


def ensure_loop() -> asyncio.AbstractEventLoop:
    """Return the global event loop, starting the executor thread if needed.

    Also recreates the loop if its backing daemon thread has died (e.g. after
    an uncaught exception escaped ``run_forever``). Without this guard a dead
    loop silently swallows every ``run_coroutine_threadsafe`` call — the exact
    failure mode behind "Feishu card not sent, no error logged".
    """
    global _loop, _executor_thread
    thread_dead = _executor_thread is not None and not _executor_thread.is_alive()
    if _loop is None or _loop.is_closed() or thread_dead:
        # Tear down the stale loop (ignore errors from an already-stopped one).
        if _loop is not None and not _loop.is_closed():
            try:
                _loop.close()
            except Exception:
                pass
        _loop = asyncio.new_event_loop()
        _executor_thread = threading.Thread(
            target=_loop.run_forever, daemon=True, name="feishu-async-executor"
        )
        _executor_thread.start()
    return _loop


def run_async(coro: Any) -> Any:
    """Schedule *coro* on the global loop and block for the result.

    If the loop has stopped running underneath us, recreate it and retry once
    so a transient loop death doesn't drop the Feishu call silently.
    """
    loop = ensure_loop()
    try:
        future = asyncio.run_coroutine_threadsafe(coro, loop)
        return future.result(timeout=35)
    except (RuntimeError, asyncio.InvalidStateError) as exc:
        msg = str(exc)
        if "not running" in msg or "closed" in msg or "loop" in msg.lower():
            global _loop, _executor_thread
            _loop = None
            _executor_thread = None
            loop = ensure_loop()
            future = asyncio.run_coroutine_threadsafe(coro, loop)
            return future.result(timeout=35)
        raise
