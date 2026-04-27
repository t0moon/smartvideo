from __future__ import annotations

from typing import Literal

from langgraph.graph import END, START, StateGraph

from app.graph.nodes.brand import node_extract_brand_profile
from app.graph.nodes.load_skills import node_load_external_skills
from app.graph.nodes.scenes import node_generate_scenes
from app.graph.nodes.audio import node_generate_audio
from app.graph.nodes.skills_llm import node_skills_storyboard_and_world
from app.graph.nodes.stitch import node_stitch_final
from app.graph.nodes.video import node_generate_clips
from app.graph.state import AgentState


def route_errors(state: AgentState) -> Literal["continue", "end"]:
    if state.get("errors"):
        return "end"
    return "continue"


def build_graph():
    builder = StateGraph(AgentState)
    builder.add_node("load_skills", node_load_external_skills)
    builder.add_node("brand", node_extract_brand_profile)
    builder.add_node("skills", node_skills_storyboard_and_world)
    builder.add_node("scenes", node_generate_scenes)
    builder.add_node("video", node_generate_clips)
    builder.add_node("audio", node_generate_audio)
    builder.add_node("stitch", node_stitch_final)

    builder.add_edge(START, "load_skills")
    builder.add_conditional_edges(
        "load_skills",
        route_errors,
        {"continue": "brand", "end": END},
    )
    builder.add_conditional_edges(
        "brand",
        route_errors,
        {"continue": "skills", "end": END},
    )
    builder.add_conditional_edges(
        "skills",
        route_errors,
        {"continue": "scenes", "end": END},
    )
    builder.add_conditional_edges(
        "scenes",
        route_errors,
        {"continue": "video", "end": END},
    )
    builder.add_conditional_edges(
        "video",
        route_errors,
        {"continue": "audio", "end": END},
    )
    builder.add_conditional_edges(
        "audio",
        route_errors,
        {"continue": "stitch", "end": END},
    )
    builder.add_edge("stitch", END)
    return builder.compile()
