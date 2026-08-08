from __future__ import annotations

from contextlib import asynccontextmanager
from typing import AsyncGenerator

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from storage.database import init_db, close_db
from app.api import router as api_router
from channels.manager import get_channel_manager
from observability.tracing.fastapi_middleware import add_tracing_middleware
from events.observability_subscriber import register_observability_subscribers
from app.config import FEISHU_ENABLED, FEISHU_CALLBACK_MODE
from channels.feishu import start_listener as start_feishu_ws
from channels.feishu import stop_listener as stop_feishu_ws
from channels.feishu.ws_listener import register_chat_event_subscribers
from channels.feishu.conversation import get_conversation_router


@asynccontextmanager
async def lifespan(app: FastAPI) -> AsyncGenerator[None, None]:
    await init_db()
    # Register observability event subscribers
    register_observability_subscribers()
    # Start channel manager
    mgr = get_channel_manager()
    mgr.ensure_channel()
    mgr.register_subscribers()
    # Initialise card-less conversation router
    get_conversation_router()
    # Start Feishu listener based on callback mode
    if FEISHU_ENABLED and FEISHU_CALLBACK_MODE == "ws":
        await start_feishu_ws()
    elif FEISHU_ENABLED and FEISHU_CALLBACK_MODE == "webhook":
        register_chat_event_subscribers()
        print("  [Feishu-Webhook] Chat event subscribers registered")
    yield
    if FEISHU_ENABLED and FEISHU_CALLBACK_MODE == "ws":
        await stop_feishu_ws()
    await mgr.shutdown()
    await close_db()


app = FastAPI(
    title="SmartVideo Platform",
    version="0.3.0",
    lifespan=lifespan,
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_methods=["*"],
    allow_headers=["*"],
)

# Add observability HTTP tracing middleware
add_tracing_middleware(app)

app.include_router(api_router, prefix="/api/v1")
