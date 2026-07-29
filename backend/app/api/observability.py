from __future__ import annotations

from typing import Any

from fastapi import APIRouter, Query
from pydantic import BaseModel

from observability import get_summary
from observability.tracing import get_tracer
from observability.logging import get_logger
from observability.metrics import get_metrics
from observability.exporter import get_exporter

router = APIRouter(prefix="/observability", tags=["observability"])


class TraceResponse(BaseModel):
    trace_id: str
    root_name: str
    span_count: int
    total_duration_ms: float
    total_cost_usd: float
    total_tokens: int
    status: str
    start_time: str


class SpanDetail(BaseModel):
    span_id: str
    trace_id: str
    parent_span_id: str | None
    name: str
    attributes: dict[str, Any]
    events: list[dict[str, Any]]
    start_time: str
    end_time: str | None
    duration_ms: float
    status: str


class LogResponse(BaseModel):
    timestamp: str
    level: str
    message: str
    project_id: str
    stage_id: str
    trace_id: str
    error: str | None
    extra: dict[str, Any]


class MetricsResponse(BaseModel):
    timestamp: str
    counters: dict[str, int]
    gauges: dict[str, float]
    timings: dict[str, dict[str, float]]
    histograms: dict[str, dict[str, float]]


@router.get("/summary")
async def get_observability_summary() -> dict[str, Any]:
    """Get a high-level overview of all observability data."""
    return get_summary()


@router.get("/traces")
async def list_traces(
    name: str | None = Query(None, description="Filter spans by name"),
    status: str | None = Query(None, description="Filter by status (ok/error)"),
    limit: int = Query(20, le=100),
) -> list[dict[str, Any]]:
    """List all trace summaries, newest first."""
    tracer = get_tracer()
    summaries: dict[str, dict[str, Any]] = {}
    for trace_id in tracer.get_all_traces():
        summary = tracer.get_trace_summary(trace_id)
        if summary:
            summaries[trace_id] = summary

    result = sorted(summaries.values(), key=lambda s: s.get("start_time", ""), reverse=True)
    if name:
        result = [s for s in result if name.lower() in s.get("root_name", "").lower()]
    if status:
        result = [s for s in result if s.get("status") == status]
    return result[:limit]


@router.get("/traces/{trace_id}")
async def get_trace(trace_id: str) -> dict[str, Any]:
    """Get full details for a specific trace."""
    tracer = get_tracer()
    spans = tracer.get_trace(trace_id)
    if not spans:
        return {"error": "Trace not found", "trace_id": trace_id}
    summary = tracer.get_trace_summary(trace_id)
    return {
        **summary,
        "spans": [s.to_dict() for s in spans],
    }


@router.get("/logs")
async def list_logs(
    level: str | None = Query(None, description="Filter by log level"),
    project_id: str | None = Query(None, description="Filter by project"),
    trace_id: str | None = Query(None, description="Filter by trace"),
    limit: int = Query(50, le=500),
) -> list[dict[str, Any]]:
    """Get structured logs with optional filters."""
    logger = get_logger()
    logs = logger.get_logs(level=level, project_id=project_id, trace_id=trace_id, limit=limit)
    return [l.to_dict() for l in logs]


@router.get("/metrics")
async def get_metrics_snapshot() -> dict[str, Any]:
    """Get current metrics snapshot."""
    return get_metrics().snapshot()


@router.post("/export")
async def export_observability() -> dict[str, Any]:
    """Export all observability data to configured exporters."""
    tracer = get_tracer()
    logger = get_logger()
    metrics = get_metrics()
    exporter = get_exporter()

    traces = tracer.export()
    logs = logger.export()
    m_snap = metrics.snapshot()

    exporter.export_traces(traces)
    exporter.export_logs(logs)
    exporter.export_metrics(m_snap)

    return {
        "exported_traces": len(traces),
        "exported_logs": len(logs),
        "exported_metrics": True,
        "exporters": [e.name for e in exporter.exporters],
    }


@router.post("/reset")
async def reset_observability() -> dict[str, str]:
    """Reset all in-memory observability data."""
    get_tracer()._spans.clear()
    get_logger().clear()
    get_metrics().reset()
    return {"status": "reset"}
