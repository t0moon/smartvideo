"""Tests for Observability system."""
from __future__ import annotations

from observability.tracing import get_tracer, TraceSpan
from observability.logging import get_logger
from observability.metrics import get_metrics
from observability.exporter import ConsoleExporter, FileExporter, LangfuseExporter
from observability import get_summary, export_all


class TestTracing:
    def _clean(self) -> None:
        t = get_tracer()
        t._spans.clear()

    def test_start_span(self) -> None:
        self._clean()
        t = get_tracer()
        span = t.start_span("test_span", {"key": "val"})
        assert span.name == "test_span"
        assert span.attributes["key"] == "val"
        assert span.span_id is not None
        assert span.trace_id is not None

    def test_end_span(self) -> None:
        self._clean()
        t = get_tracer()
        span = t.start_span("test")
        t.end_span(span, "ok")
        assert span.status == "ok"
        assert span.duration_ms >= 0

    def test_trace_hierarchy(self) -> None:
        self._clean()
        t = get_tracer()
        parent = t.start_span("parent")
        child = t.start_span("child", parent_span=parent)
        assert child.trace_id == parent.trace_id
        assert child.parent_span_id == parent.span_id

    def test_get_trace(self) -> None:
        self._clean()
        t = get_tracer()
        span = t.start_span("s1")
        spans = t.get_trace(span.trace_id)
        assert len(spans) == 1
        assert spans[0].span_id == span.span_id

    def test_export(self) -> None:
        self._clean()
        t = get_tracer()
        t.start_span("export_test")
        exported = t.export()
        assert len(exported) >= 1
        assert exported[0]["name"] == "export_test"

    def test_add_event(self) -> None:
        self._clean()
        span = TraceSpan("test_span")
        span.add_event("test.event", {"key": "val"})
        assert len(span.events) == 1
        assert span.events[0]["name"] == "test.event"
        assert span.events[0]["attributes"]["key"] == "val"

    def test_record_llm_call(self) -> None:
        self._clean()
        span = TraceSpan("llm_call")
        span.record_llm_call("gpt-4o-mini", 100, 50, 200.0)
        assert span.attributes["llm.model"] == "gpt-4o-mini"
        assert span.attributes["llm.input_tokens"] == 100
        assert span.attributes["llm.output_tokens"] == 50
        assert span.attributes["llm.cost_usd"] > 0
        assert len(span.events) >= 1
        assert span.events[0]["name"] == "llm.call"

    def test_search_spans(self) -> None:
        self._clean()
        t = get_tracer()
        t.start_span("pipeline.run")
        t.start_span("stage.requirement")
        found = t.search_spans(name="pipeline")
        assert len(found) >= 1
        assert found[0].name == "pipeline.run"

    def test_get_trace_summary(self) -> None:
        self._clean()
        t = get_tracer()
        span = t.start_span("root", {"project_id": "p1"})
        t.end_span(span)
        summary = t.get_trace_summary(span.trace_id)
        assert summary["root_name"] == "root"
        assert summary["span_count"] >= 1

    def test_get_all_spans(self) -> None:
        self._clean()
        t = get_tracer()
        t.start_span("s1")
        t.start_span("s2")
        spans = t.get_all_spans()
        assert len(spans) >= 2

    def test_to_dict(self) -> None:
        span = TraceSpan("test", attributes={"key": "val"})
        span.end()
        d = span.to_dict()
        assert d["name"] == "test"
        assert d["attributes"]["key"] == "val"
        assert d["duration_ms"] >= 0
        assert d["status"] == "ok"


class TestLogging:
    def _clean(self) -> None:
        l = get_logger()
        l.clear()

    def test_info(self) -> None:
        self._clean()
        l = get_logger()
        l.info("p1", "s1", "test message", extra_field="val")
        logs = l.get_logs()
        assert len(logs) == 1
        assert logs[0].level == "INFO"
        assert logs[0].message == "test message"

    def test_error(self) -> None:
        self._clean()
        l = get_logger()
        l.error("p1", "s1", "error msg", error="something broke")
        logs = l.get_logs(level="ERROR")
        assert len(logs) == 1

    def test_filter(self) -> None:
        self._clean()
        l = get_logger()
        l.info("p1", "s1", "msg1")
        l.info("p2", "s1", "msg2")
        logs = l.get_logs(project_id="p1")
        assert len(logs) == 1

    def test_export(self) -> None:
        self._clean()
        l = get_logger()
        l.info("p1", "s1", "export test")
        exported = l.export()
        assert len(exported) == 1
        assert exported[0]["level"] == "INFO"

    def test_trace_id(self) -> None:
        self._clean()
        l = get_logger()
        l.info("p1", "s1", "trace msg", trace_id="trace_123")
        logs = l.get_logs(trace_id="trace_123")
        assert len(logs) == 1
        assert logs[0].trace_id == "trace_123"

    def test_debug_warning(self) -> None:
        self._clean()
        l = get_logger()
        l.debug("p1", "s1", "debug msg")
        l.warning("p1", "s1", "warning msg")
        logs = l.get_logs()
        assert len(logs) == 2


class TestMetrics:
    def _clean(self) -> None:
        m = get_metrics()
        m.reset()

    def test_increment(self) -> None:
        self._clean()
        m = get_metrics()
        m.increment("pipeline.run")
        m.increment("pipeline.run")
        snap = m.snapshot()
        assert snap["counters"]["pipeline.run"] == 2

    def test_gauge(self) -> None:
        self._clean()
        m = get_metrics()
        m.gauge("active.projects", 5.0)
        snap = m.snapshot()
        assert snap["gauges"]["active.projects"] == 5.0

    def test_timing(self) -> None:
        self._clean()
        m = get_metrics()
        m.timing("stage.duration", 150.0)
        m.timing("stage.duration", 250.0)
        snap = m.snapshot()
        assert snap["timings"]["stage.duration"]["count"] == 2
        assert snap["timings"]["stage.duration"]["avg"] == 200.0

    def test_increment_with_tags(self) -> None:
        self._clean()
        m = get_metrics()
        m.increment("stage.completed", {"stage": "requirement"})
        m.increment("stage.completed", {"stage": "storyboard"})
        snap = m.snapshot()
        assert len(snap["counters"]) == 2

    def test_histogram(self) -> None:
        self._clean()
        m = get_metrics()
        m.histogram("llm.input_tokens", 150, {"model": "gpt-4o"})
        m.histogram("llm.input_tokens", 250, {"model": "gpt-4o"})
        snap = m.snapshot()
        hist_key = "llm.input_tokens[model=gpt-4o]"
        assert hist_key in snap["histograms"]
        assert snap["histograms"][hist_key]["count"] == 2
        assert snap["histograms"][hist_key]["avg"] == 200.0

    def test_record_llm_usage(self) -> None:
        self._clean()
        m = get_metrics()
        m.record_llm_usage("gpt-4o-mini", 100, 50, 0.0001)
        snap = m.snapshot()
        assert snap["counters"]["llm.call_count[model=gpt-4o-mini]"] == 1

    def test_get_counter(self) -> None:
        self._clean()
        m = get_metrics()
        m.increment("test.counter")
        assert m.get_counter("test.counter") == 1


class TestExporter:
    def test_console_exporter(self) -> None:
        e = ConsoleExporter()
        assert e.name == "console"

    def test_export_traces(self) -> None:
        e = ConsoleExporter()
        e.export_traces([{"name": "test", "duration_ms": 100, "status": "ok", "attributes": {}}])

    def test_export_logs(self) -> None:
        e = ConsoleExporter()
        e.export_logs([{"level": "INFO", "project_id": "p1", "message": "test"}])

    def test_export_metrics(self) -> None:
        e = ConsoleExporter()
        e.export_metrics({"counters": {"c1": 1}, "timings": {}, "histograms": {}})

    def test_file_exporter(self) -> None:
        import tempfile
        from pathlib import Path
        with tempfile.TemporaryDirectory() as d:
            e = FileExporter(Path(d))
            e.export_traces([{"name": "t1", "span_id": "s1"}])
            e.export_logs([{"level": "INFO", "message": "test"}])
            e.export_metrics({"counters": {"c1": 1}, "timings": {}, "histograms": {}})
            files = list(Path(d).iterdir())
            assert len(files) >= 1

    def test_langfuse_exporter_disabled(self) -> None:
        e = LangfuseExporter()
        e.export_traces([])
        e.export_traces([{"name": "t1", "trace_id": "tid1"}])


class TestObservabilityModule:
    def _clean(self) -> None:
        get_tracer()._spans.clear()
        get_logger().clear()
        get_metrics().reset()

    def test_get_summary(self) -> None:
        self._clean()
        t = get_tracer()
        span = t.start_span("test.root")
        t.end_span(span)
        get_logger().info("p1", "s1", "test log")
        get_metrics().increment("test.counter")
        summary = get_summary()
        assert summary["trace_count"] >= 1
        assert summary["span_count"] >= 1
        assert summary["log_count"] >= 1
        assert "recent_spans" in summary

    def test_export_all(self) -> None:
        self._clean()
        t = get_tracer()
        span = t.start_span("export")
        t.end_span(span)
        result = export_all()
        assert "traces" in result
        assert "logs" in result
        assert "metrics" in result
