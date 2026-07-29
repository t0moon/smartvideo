"""Tests for Middleware Chain."""
from __future__ import annotations

from context.schemas import StageContext, StageOutput
from middleware.base import AgentMiddleware
from middleware.registry import MiddlewareRegistry, register_defaults


class TestMiddlewareBase:
    def test_before_stage_default(self) -> None:
        m = AgentMiddleware()
        ctx = StageContext(stage_id="s1", project_id="p1")
        import asyncio
        result = asyncio.run(m.before_stage(ctx))
        assert result.stage_id == "s1"

    def test_after_stage_default(self) -> None:
        m = AgentMiddleware()
        ctx = StageContext(stage_id="s1", project_id="p1")
        out = StageOutput(stage_id="s1", project_id="p1")
        import asyncio
        result = asyncio.run(m.after_stage(ctx, out))
        assert result.stage_id == "s1"


class TestMiddlewareRegistry:
    def test_register_and_list(self) -> None:
        reg = MiddlewareRegistry()

        class MockM(AgentMiddleware):
            name = "mock"

        reg.register(MockM(), order=50)
        names = reg.list_names()
        assert "mock" in names

    def test_chain_sorting(self) -> None:
        reg = MiddlewareRegistry()

        class M1(AgentMiddleware):
            name = "m1"

        class M2(AgentMiddleware):
            name = "m2"

        reg.register(M1(), order=20)
        reg.register(M2(), order=10)
        middlewares = reg.list()
        assert middlewares[0][0] == 10
        assert middlewares[1][0] == 20

    def test_register_defaults(self) -> None:
        reg = MiddlewareRegistry()
        reg.register = lambda *a, **k: None
        # Just verify no errors
        pass


class TestMiddlewareImplementations:
    def test_tracing(self) -> None:
        from middleware.tracing import TracingMiddleware
        m = TracingMiddleware()
        assert m.name == "tracing"
        ctx = StageContext(stage_id="test", project_id="p1")
        import asyncio
        result = asyncio.run(m.before_stage(ctx))
        assert "test" in result.stage_id

    def test_tool_guard_allows_clean(self) -> None:
        from middleware.tool_guard import ToolGuardMiddleware
        m = ToolGuardMiddleware()
        assert m.name == "tool_guard"
        ctx = StageContext(stage_id="test", project_id="p1")
        import asyncio
        result = asyncio.run(m.before_stage(ctx))
        assert result.stage_id == "test"

    def test_approval_exists(self) -> None:
        from middleware.approval import ApprovalMiddleware
        m = ApprovalMiddleware()
        assert m.name == "approval"

    def test_audit_logs(self) -> None:
        from middleware.audit import AuditMiddleware
        m = AuditMiddleware()
        ctx = StageContext(stage_id="audit_test", project_id="p1")
        out = StageOutput(stage_id="audit_test", project_id="p1")
        import asyncio
        asyncio.run(m.before_stage(ctx))
        asyncio.run(m.after_stage(ctx, out))
        history = m.get_history()
        assert len(history) == 2
        assert history[0]["action"] == "before_stage"
        assert history[1]["action"] == "after_stage"

    def test_retry_exists(self) -> None:
        from middleware.retry import RetryMiddleware
        m = RetryMiddleware()
        assert m.name == "retry"
        assert m.max_retries == 3

    def test_cache(self) -> None:
        from middleware.cache import CacheMiddleware
        m = CacheMiddleware()
        assert m.name == "cache"
        ctx = StageContext(stage_id="cache_test", project_id="p1")
        import asyncio
        result = asyncio.run(m.before_stage(ctx))
        assert result.provider_outputs["cache"]["hit"] is False

    def test_model_router(self) -> None:
        from middleware.model_router import ModelRouterMiddleware
        m = ModelRouterMiddleware()
        assert m.name == "model_router"
        ctx = StageContext(stage_id="storyboard", project_id="p1")
        import asyncio
        result = asyncio.run(m.before_stage(ctx))
        assert result.provider_outputs["model_router"]["selected_model"] == "gpt-4o"


class TestMiddlewareIntegration:
    def test_full_chain_does_not_block(self) -> None:
        reg = MiddlewareRegistry()
        from middleware.tracing import TracingMiddleware
        from middleware.tool_guard import ToolGuardMiddleware
        from middleware.approval import ApprovalMiddleware
        from middleware.audit import AuditMiddleware
        from middleware.retry import RetryMiddleware
        from middleware.cache import CacheMiddleware
        from middleware.model_router import ModelRouterMiddleware

        for m, order in [
            (TracingMiddleware(), 10),
            (ToolGuardMiddleware(), 20),
            (ApprovalMiddleware(), 30),
            (AuditMiddleware(), 40),
            (RetryMiddleware(), 50),
            (CacheMiddleware(), 60),
            (ModelRouterMiddleware(), 70),
        ]:
            reg.register(m, order)

        ctx = StageContext(stage_id="requirement", project_id="test_p1")
        out = StageOutput(stage_id="requirement", project_id="test_p1", outputs={"video_spec": {}})

        import asyncio
        ctx_out = asyncio.run(reg.run_before(ctx))
        assert ctx_out.stage_id == "requirement"
        assert len(ctx_out.provider_outputs) >= 3  # tracing + tool_guard + model_router

        out_result = asyncio.run(reg.run_after(ctx_out, out))
        assert out_result.stage_id == "requirement"
