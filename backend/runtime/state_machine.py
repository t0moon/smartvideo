from __future__ import annotations

from datetime import datetime, timezone
from enum import Enum
from typing import Any


class StageState(str, Enum):
    PENDING = 'pending'
    RUNNING = 'running'
    PAUSED = 'paused'
    COMPLETED = 'completed'
    FAILED = 'failed'
    SKIPPED = 'skipped'


class StageNode:
    def __init__(self, stage_id: str, config: dict[str, Any]) -> None:
        self.stage_id: str = stage_id
        self.config: dict[str, Any] = config
        self.state: StageState = StageState.PENDING
        self.output: dict[str, Any] | None = None
        self.error: str | None = None
        self.started_at: datetime | None = None
        self.completed_at: datetime | None = None

    def start(self) -> None:
        self.state = StageState.RUNNING
        self.started_at = datetime.now(timezone.utc)

    def complete(self, output: dict[str, Any]) -> None:
        self.state = StageState.COMPLETED
        self.output = output
        self.completed_at = datetime.now(timezone.utc)

    def fail(self, error: str) -> None:
        self.state = StageState.FAILED
        self.error = error
        self.completed_at = datetime.now(timezone.utc)

    def pause(self) -> None:
        self.state = StageState.PAUSED

    def resume(self) -> None:
        self.state = StageState.RUNNING


class WorkflowStateMachine:
    def __init__(self, workflow_name: str = '') -> None:
        self.workflow_name: str = workflow_name
        self.stages: dict[str, StageNode] = {}
        self.edges: dict[str, list[str]] = {}
        self.current_stage_id: str | None = None
        self.status: str = 'created'

    def add_stage(self, stage_id: str, config: dict[str, Any]) -> StageNode:
        node = StageNode(stage_id, config)
        self.stages[stage_id] = node
        return node

    def add_edge(self, from_stage: str, to_stage: str | None) -> None:
        if from_stage not in self.edges:
            self.edges[from_stage] = []
        if to_stage:
            self.edges[from_stage].append(to_stage)

    def get_stage(self, stage_id: str) -> StageNode | None:
        return self.stages.get(stage_id)

    def start_stage(self, stage_id: str) -> StageNode | None:
        node = self.stages.get(stage_id)
        if node:
            node.start()
            self.current_stage_id = stage_id
        return node

    def complete_stage(self, stage_id: str, output: dict[str, Any]) -> StageNode | None:
        node = self.stages.get(stage_id)
        if node:
            node.complete(output)
        return node

    def fail_stage(self, stage_id: str, error: str) -> StageNode | None:
        node = self.stages.get(stage_id)
        if node:
            node.fail(error)
        return node

    def pause_stage(self, stage_id: str) -> StageNode | None:
        node = self.stages.get(stage_id)
        if node:
            node.pause()
        return node

    def resume_stage(self, stage_id: str) -> StageNode | None:
        node = self.stages.get(stage_id)
        if node:
            node.resume()
        return node

    def get_next_stages(self, stage_id: str) -> list[str]:
        return self.edges.get(stage_id, [])

    def get_first_stage(self) -> str | None:
        for sid, edges in self.edges.items():
            is_child = False
            for targets in self.edges.values():
                if sid in targets:
                    is_child = True
                    break
            if not is_child:
                return sid
        return None

    def get_ordered_stages(self) -> list[str]:
        ordered: list[str] = []
        visited: set[str] = set()

        def dfs(sid: str) -> None:
            if sid in visited:
                return
            visited.add(sid)
            ordered.append(sid)
            for next_sid in self.edges.get(sid, []):
                dfs(next_sid)

        first = self.get_first_stage()
        if first:
            dfs(first)
        return ordered

    def is_completed(self) -> bool:
        return all(
            node.state in (StageState.COMPLETED, StageState.SKIPPED)
            for node in self.stages.values()
        )

    def is_paused(self) -> bool:
        return any(node.state == StageState.PAUSED for node in self.stages.values())

    def to_dict(self) -> dict[str, Any]:
        return {
            'workflow_name': self.workflow_name,
            'status': self.status,
            'current_stage_id': self.current_stage_id,
            'stages': {
                sid: {
                    'state': node.state.value,
                    'error': node.error,
                    'started_at': str(node.started_at) if node.started_at else None,
                    'completed_at': str(node.completed_at) if node.completed_at else None,
                }
                for sid, node in self.stages.items()
            },
        }
