from __future__ import annotations

import json
from datetime import datetime, timezone
from pathlib import Path
from typing import Any
from urllib.request import Request, urlopen

from observability.tracing import get_tracer
from observability.metrics import get_metrics


class BaseExporter:
    name: str = "base"

    def export_traces(self, traces: list[dict[str, Any]]) -> None:
        raise NotImplementedError

    def export_logs(self, logs: list[dict[str, Any]]) -> None:
        raise NotImplementedError

    def export_metrics(self, metrics: dict[str, Any]) -> None:
        raise NotImplementedError


class ConsoleExporter(BaseExporter):
    name = "console"

    def export_traces(self, traces: list[dict[str, Any]]) -> None:
        for t in traces:
            n = t.get("name", "?")
            d = t.get("duration_ms", 0)
            s = t.get("status", "?")
            cost = t.get("attributes", {}).get("llm.cost_usd", 0)
            cost_str = f" ${cost}" if cost else ""
            print(f"  [Trace] {n} ({d}ms){cost_str} [{s}]")

    def export_logs(self, logs: list[dict[str, Any]]) -> None:
        for l in logs:
            lv = l.get("level", "?")
            pid = l.get("project_id", "?")
            msg = l.get("message", "?")
            print(f"  [{lv}] [{pid}] {msg}")

    def export_metrics(self, metrics: dict[str, Any]) -> None:
        counters = metrics.get("counters", {})
        timings = metrics.get("timings", {})
        histograms = metrics.get("histograms", {})
        print(f"  [Metrics] {len(counters)} counters, {len(timings)} timings, {len(histograms)} histograms")


class FileExporter(BaseExporter):
    name = "file"

    def __init__(self, output_dir: Path | None = None) -> None:
        from app.config import DATA_DIR
        self.output_dir = output_dir or (DATA_DIR / "exports")
        self.output_dir.mkdir(parents=True, exist_ok=True)

    def _write(self, prefix: str, data: Any) -> None:
        ts = datetime.now(timezone.utc).strftime("%Y%m%d_%H%M%S")
        path = self.output_dir / f"{prefix}_{ts}.json"
        path.write_text(json.dumps(data, ensure_ascii=False, indent=2, default=str), encoding="utf-8")
        print(f"  [FileExporter] Wrote {len(data)} items to {path}")

    def export_traces(self, traces: list[dict[str, Any]]) -> None:
        self._write("traces", traces)

    def export_logs(self, logs: list[dict[str, Any]]) -> None:
        self._write("logs", logs)

    def export_metrics(self, metrics: dict[str, Any]) -> None:
        self._write("metrics", metrics)


class LangfuseExporter(BaseExporter):
    """Exports traces to Langfuse via their public API.

    Requires LANGFUSE_HOST, LANGFUSE_PUBLIC_KEY, LANGFUSE_SECRET_KEY in env.
    Falls back silently if not configured.
    """
    name = "langfuse"

    def __init__(self) -> None:
        import os
        self.host = os.getenv("LANGFUSE_HOST", "").rstrip("/")
        self.public_key = os.getenv("LANGFUSE_PUBLIC_KEY", "")
        self.secret_key = os.getenv("LANGFUSE_SECRET_KEY", "")
        self.enabled = bool(self.host and self.public_key and self.secret_key)
        if self.enabled:
            import base64
            auth = f"{self.public_key}:{self.secret_key}"
            self._auth_header = f"Basic {base64.b64encode(auth.encode()).decode()}"

    def _post(self, path: str, body: dict[str, Any]) -> None:
        if not self.enabled:
            return
        url = f"{self.host}/api/public/{path}"
        data = json.dumps(body).encode()
        req = Request(url, data=data, method="POST", headers={
            "Authorization": self._auth_header,
            "Content-Type": "application/json",
        })
        try:
            with urlopen(req, timeout=5) as resp:
                resp.read()
        except Exception as exc:
            print(f"  [LangfuseExporter] Error: {exc}")

    def export_traces(self, traces: list[dict[str, Any]]) -> None:
        if not self.enabled or not traces:
            return
        for t in traces:
            attrs = t.get("attributes", {})
            generation = {
                "name": t.get("name", "unknown"),
                "traceId": t.get("trace_id", ""),
                "spanId": t.get("span_id", ""),
                "parentSpanId": t.get("parent_span_id"),
                "startTime": t.get("start_time", ""),
                "endTime": t.get("end_time", ""),
                "metadata": attrs,
                "status": "completed" if t.get("status") == "ok" else "error",
            }
            # Add LLM cost info if present
            if "llm.cost_usd" in attrs:
                generation["cost"] = attrs["llm.cost_usd"]
                generation["usage"] = {
                    "input": attrs.get("llm.input_tokens", 0),
                    "output": attrs.get("llm.output_tokens", 0),
                }
            self._post("generations", generation)

    def export_logs(self, logs: list[dict[str, Any]]) -> None:
        pass  # Langfuse doesn't have a direct log ingestion API

    def export_metrics(self, metrics: dict[str, Any]) -> None:
        pass


class LangSmithExporter(BaseExporter):
    """Exports traces to LangSmith.

    Requires LANGCHAIN_API_KEY, LANGCHAIN_PROJECT in env.
    """
    name = "langsmith"

    def __init__(self) -> None:
        import os
        self.api_key = os.getenv("LANGCHAIN_API_KEY", "")
        self.project = os.getenv("LANGCHAIN_PROJECT", "smartvideo")
        self.endpoint = os.getenv("LANGCHAIN_ENDPOINT", "https://api.smith.langchain.com")
        self.enabled = bool(self.api_key)

    def export_traces(self, traces: list[dict[str, Any]]) -> None:
        if not self.enabled or not traces:
            return
        print(f"  [LangSmithExporter] Skipping batch of {len(traces)} spans (SDK integration pending)")
        # Full LangSmith integration requires langchain SDK which adds heavy deps.
        # This is a placeholder for when you install langsmith package.

    def export_logs(self, logs: list[dict[str, Any]]) -> None:
        pass

    def export_metrics(self, metrics: dict[str, Any]) -> None:
        pass


class CompositeExporter(BaseExporter):
    """Runs multiple exporters together."""

    def __init__(self, exporters: list[BaseExporter] | None = None) -> None:
        self.exporters = exporters or [ConsoleExporter()]

    def add(self, exporter: BaseExporter) -> None:
        self.exporters.append(exporter)

    def export_traces(self, traces: list[dict[str, Any]]) -> None:
        for e in self.exporters:
            try:
                e.export_traces(traces)
            except Exception as exc:
                print(f"  [{e.name}] export_traces error: {exc}")

    def export_logs(self, logs: list[dict[str, Any]]) -> None:
        for e in self.exporters:
            try:
                e.export_logs(logs)
            except Exception as exc:
                print(f"  [{e.name}] export_logs error: {exc}")

    def export_metrics(self, metrics: dict[str, Any]) -> None:
        for e in self.exporters:
            try:
                e.export_metrics(metrics)
            except Exception as exc:
                print(f"  [{e.name}] export_metrics error: {exc}")


def create_default_exporter() -> CompositeExporter:
    """Create a composite exporter with console + file + langfuse (if configured)."""
    composite = CompositeExporter([ConsoleExporter(), FileExporter()])
    langfuse = LangfuseExporter()
    if langfuse.enabled:
        composite.add(langfuse)
    langsmith = LangSmithExporter()
    if langsmith.enabled:
        composite.add(langsmith)
    return composite


def get_exporter() -> CompositeExporter:
    return _exporter if "_exporter" in dir() else create_default_exporter()


_exporter = create_default_exporter()
