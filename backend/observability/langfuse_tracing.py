"""Langfuse tracing integration for SmartVideo platform.

Provides context managers for pipeline-level tracing and stage-level spans.
Auto-instrumented OpenAI calls (via langfuse.openai) automatically nest under the
current Langfuse span context.

Usage:
    with pipeline_trace(project_id="abc", brief="make a video") as trace_id:
        with stage_span("requirement", input={"model": "gpt-4o-mini"}):
            agent.understand_requirement("...")
        with stage_span("storyboard", input={"scenes": 5}):
            agent.generate_storyboard(spec, brand)
"""

from __future__ import annotations

from contextlib import contextmanager
from typing import Any, Iterator

from langfuse import Langfuse

_langfuse_instance: Langfuse | None = None


def get_langfuse() -> Langfuse:
    """Get or create the singleton Langfuse client.

    Langfuse reads LANGFUSE_PUBLIC_KEY, LANGFUSE_SECRET_KEY, LANGFUSE_HOST
    from environment variables (already loaded by app.config).
    """
    global _langfuse_instance
    if _langfuse_instance is None:
        _langfuse_instance = Langfuse()
    return _langfuse_instance


def reset_langfuse() -> None:
    """Reset the Langfuse client singleton (useful for testing)."""
    global _langfuse_instance
    if _langfuse_instance is not None:
        _langfuse_instance.shutdown()
        _langfuse_instance = None


@contextmanager
def pipeline_trace(project_id: str, brief: str = "") -> Iterator[str]:
    """Context manager: creates a root Langfuse trace for a full pipeline run.

    Auto-nests all OpenAI calls and stage spans within this trace.

    Yields:
        The Langfuse trace ID for correlation.
    """
    lf = get_langfuse()
    trace_id = lf.create_trace_id()
    with lf.start_as_current_observation(
        name=f"pipeline.{project_id}",
        trace_context={"trace_id": trace_id},
        as_type="chain",
        input={"project_id": project_id, "brief_len": len(brief)},
        end_on_exit=True,
    ):
        yield trace_id


@contextmanager
def stage_span(stage_name: str, stage_input: dict[str, Any] | None = None) -> Iterator[None]:
    """Context manager: creates a stage span auto-nested under the current parent.

    Must be used inside a pipeline_trace() context (or another stage_span).
    OpenAI calls made inside this context will be auto-nested as child generations.

    Args:
        stage_name: Name for the span (e.g. "requirement", "storyboard").
        stage_input: Optional dict of input parameters for the span.
    """
    lf = get_langfuse()
    with lf.start_as_current_observation(
        name=stage_name,
        as_type="chain",
        input=stage_input or {},
        end_on_exit=True,
    ):
        yield


@contextmanager
def stage_agent_span(agent_name: str, agent_input: dict[str, Any] | None = None) -> Iterator[None]:
    """Context manager: creates an agent-type span for subagent operations.

    Use this for LeadAgent or SubAgent calls to get proper agent graph visualization.
    """
    lf = get_langfuse()
    with lf.start_as_current_observation(
        name=agent_name,
        as_type="agent",
        input=agent_input or {},
        end_on_exit=True,
    ):
        yield


def update_trace_output(output: dict[str, Any]) -> None:
    """Update the current trace's output with the pipeline result."""
    # In Langfuse v4 SDK, trace IO is auto-managed via start_as_current_observation
    # Use update_current_span for the current chain/span
    lf = get_langfuse()
    lf.update_current_span(output=output)


def flush_traces() -> None:
    """Flush all pending traces/spans to Langfuse."""
    lf = get_langfuse()
    lf.flush()
