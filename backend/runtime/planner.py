from __future__ import annotations

from typing import Any

from runtime.state_machine import StageNode


class WorkflowPlanner:
    def __init__(self, edges: dict[str, list[str]]) -> None:
        self.edges = edges

    def get_next(self, current_stage_id: str, outputs: dict[str, Any]) -> str | None:
        next_stages = self.edges.get(current_stage_id, [])
        if not next_stages:
            return None

        # If there are conditions in outputs, handle them
        branch = outputs.get('_branch')
        if branch and branch in next_stages:
            return branch

        return next_stages[0]

    def get_parallel_targets(self, current_stage_id: str) -> list[str]:
        return self.edges.get(current_stage_id, [])

    @staticmethod
    def should_pause(node: StageNode) -> bool:
        return node.config.get('pause_for_review', False)

    @staticmethod
    def should_skip(node: StageNode, previous_outputs: dict[str, Any]) -> bool:
        condition = node.config.get('condition')
        if condition:
            return not previous_outputs.get(condition, False)
        return False
