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
    """Return the global event loop, starting the executor thread if needed."""
    global _loop, _executor_thread
    if _loop is None or _loop.is_closed():
        _loop = asyncio.new_event_loop()
        _executor_thread = threading.Thread(
            target=_loop.run_forever, daemon=True, name="feishu-async-executor"
        )
        _executor_thread.start()
    return _loop


def run_async(coro: Any) -> Any:
    """Schedule *coro* on the global loop and block for the result."""
    loop = ensure_loop()
    future = asyncio.run_coroutine_threadsafe(coro, loop)
    return future.result(timeout=35)
