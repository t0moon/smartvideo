from __future__ import annotations

from observability.tracing import get_tracer
from observability.logging import get_logger
from observability.metrics import get_metrics
from observability.exporter import ConsoleExporter, FileExporter

__all__ = [
    "TraceSpan",
    "Tracer",
    "get_tracer",
    "LogEntry",
    "StructuredLogger",
    "get_logger",
    "MetricsCollector",
    "get_metrics",
    "ConsoleExporter",
    "FileExporter",
    "export_all",
    "get_summary",
]

from observability.tracing import TraceSpan, Tracer
from observability.logging import LogEntry, StructuredLogger


def export_all() -> dict[str, Any]:
    """Export all observability data as a single dict."""
    return {
        "traces": get_tracer().export(),
        "logs": get_logger().export(),
        "metrics": get_metrics().snapshot(),
    }


def get_summary() -> dict[str, Any]:
    """Get a high-level summary of all observability data."""
    tracer = get_tracer()
    metrics = get_metrics()
    all_spans = tracer.get_all_spans()
    span_count = len(all_spans)
    trace_ids = set(s.trace_id for s in all_spans)

    total_cost = 0.0
    total_tokens = 0
    for s in all_spans:
        total_cost += s.attributes.get("llm.cost_usd", 0) or 0
        total_tokens += s.attributes.get("llm.total_tokens", 0) or 0

    return {
        "trace_count": len(trace_ids),
        "span_count": span_count,
        "total_cost_usd": round(total_cost, 6),
        "total_tokens": total_tokens,
        "log_count": len(get_logger()._logs),
        "metrics_snapshot": metrics.snapshot(),
        "recent_spans": [
            {"trace_id": s.trace_id, "name": s.name, "duration_ms": s.duration_ms, "status": s.status}
            for s in all_spans[:20]
        ],
    }


def export_and_cleanup() -> None:
    """Export to console + file, then reset in-memory state."""
    tracer = get_tracer()
    logger = get_logger()
    metrics = get_metrics()

    console = ConsoleExporter()
    file_exp = FileExporter()

    traces = tracer.export()
    logs = logger.export()
    m_snap = metrics.snapshot()

    file_exp.export_traces(traces)
    file_exp.export_logs(logs)
    file_exp.export_metrics(m_snap)

    console.export_traces(traces[-5:])
    console.export_logs(logs[-5:])
    console.export_metrics(m_snap)

    tracer._spans.clear()
    logger.clear()
    metrics.reset()
