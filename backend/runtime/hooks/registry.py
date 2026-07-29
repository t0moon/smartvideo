from __future__ import annotations

from typing import Any

from runtime.hooks.base import PipelineHook


class HookRegistry:
    def __init__(self) -> None:
        self._hooks: dict[str, PipelineHook] = {}

    def register(self, hook: PipelineHook) -> None:
        self._hooks[hook.name] = hook

    def get(self, name: str) -> PipelineHook | None:
        return self._hooks.get(name)

    def list(self) -> list[PipelineHook]:
        return list(self._hooks.values())

    async def run_after_stage(self, project_id: str, stage_id: str, context: dict[str, Any]) -> None:
        for hook in self._hooks.values():
            await hook.after_stage(project_id, stage_id, context)

    async def run_after_pipeline(self, project_id: str, context: dict[str, Any]) -> None:
        for hook in self._hooks.values():
            await hook.after_pipeline(project_id, context)


_registry = HookRegistry()


def get_registry() -> HookRegistry:
    return _registry


def register_hook(hook: PipelineHook) -> None:
    _registry.register(hook)
