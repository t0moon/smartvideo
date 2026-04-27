from __future__ import annotations

from typing import Annotated, Any, TypedDict

from langgraph.graph.message import add_messages


class AgentState(TypedDict, total=False):
    messages: Annotated[list[Any], add_messages]
    brand_profile: dict[str, Any]
    skill_docs: dict[str, str]
    skill_meta: dict[str, Any]
    storyboard_template: dict[str, Any]
    world_constraints: dict[str, Any]
    scenes: list[dict[str, Any]]
    clips: dict[str, str]
    artifact_run_id: str
    final_video_path: str
    errors: list[dict[str, Any]]
