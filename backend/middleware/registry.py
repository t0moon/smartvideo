from __future__ import annotations

from typing import Any

from middleware.base import AgentMiddleware
from context.schemas import StageContext, StageOutput


class MiddlewareRegistry:
    def __init__(self) -> None:
        self._middlewares: list[tuple[int, AgentMiddleware]] = []

    def register(self, middleware: AgentMiddleware, order: int = 0) -> None:
        self._middlewares.append((order, middleware))
        self._middlewares.sort(key=lambda x: x[0])

    def list(self) -> list[tuple[int, AgentMiddleware]]:
        return list(self._middlewares)

    def list_names(self) -> list[str]:
        return [m.name for _, m in self._middlewares]

    async def run_before(self, ctx: StageContext) -> StageContext:
        for _, m in self._middlewares:
            ctx = await m.before_stage(ctx)
        return ctx

    async def run_after(self, ctx: StageContext, output: StageOutput) -> StageOutput:
        for _, m in reversed(self._middlewares):
            output = await m.after_stage(ctx, output)
        return output

    def get(self, name: str) -> AgentMiddleware | None:
        for _, m in self._middlewares:
            if m.name == name:
                return m
        return None


_registry = MiddlewareRegistry()


def get_registry() -> MiddlewareRegistry:
    return _registry


def register_defaults() -> None:
    from middleware.tracing import TracingMiddleware
    from middleware.tool_guard import ToolGuardMiddleware
    from middleware.approval import ApprovalMiddleware
    from middleware.audit import AuditMiddleware
    from middleware.retry import RetryMiddleware
    from middleware.cache import CacheMiddleware
    from middleware.model_router import ModelRouterMiddleware
    _registry.register(TracingMiddleware(), order=10)
    _registry.register(ToolGuardMiddleware(), order=20)
    _registry.register(ApprovalMiddleware(), order=30)
    _registry.register(AuditMiddleware(), order=40)
    _registry.register(RetryMiddleware(), order=50)
    _registry.register(CacheMiddleware(), order=60)
    _registry.register(ModelRouterMiddleware(), order=70)
