from __future__ import annotations

from typing import Any

from subagents.base import BaseSubagent


class SubagentRegistry:
    def __init__(self) -> None:
        self._agents: dict[str, BaseSubagent] = {}

    def register(self, agent: BaseSubagent) -> None:
        self._agents[agent.name] = agent

    def get(self, name: str) -> BaseSubagent | None:
        return self._agents.get(name)

    def list_names(self) -> list[str]:
        return list(self._agents.keys())

    def execute_all(self, tasks: list[dict[str, Any]], context: dict[str, Any]) -> list[dict[str, Any]]:
        import asyncio
        results: list[dict[str, Any]] = []
        for task in tasks:
            agent_name = task.get('agent', '')
            agent = self._agents.get(agent_name)
            if agent:
                result = asyncio.run(agent.execute(task, context))
                results.append(result)
        return results


_registry = SubagentRegistry()


def get_registry() -> SubagentRegistry:
    return _registry


def register(agent: BaseSubagent) -> None:
    _registry.register(agent)
