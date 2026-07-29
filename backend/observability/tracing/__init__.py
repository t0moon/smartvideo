from __future__ import annotations

import uuid
from datetime import datetime, timezone
from typing import Any


_LLM_COST_PER_MODEL: dict[str, dict[str, float]] = {
    'gpt-4o': {'input': 2.50 / 1_000_000, 'output': 10.00 / 1_000_000},
    'gpt-4o-mini': {'input': 0.150 / 1_000_000, 'output': 0.600 / 1_000_000},
    'gpt-4o-mini-tts': {'input': 0.150 / 1_000_000, 'output': 0.600 / 1_000_000},
    'gpt-4o-audio-preview': {'input': 2.50 / 1_000_000, 'output': 10.00 / 1_000_000},
    'deepseek-chat': {'input': 0.14 / 1_000_000, 'output': 0.28 / 1_000_000},
    'deepseek-reasoner': {'input': 0.55 / 1_000_000, 'output': 2.19 / 1_000_000},
}


def _estimate_cost(model: str, input_tokens: int, output_tokens: int) -> float:
    """Estimate cost in USD for an LLM call."""
    pricing = _LLM_COST_PER_MODEL.get(model, _LLM_COST_PER_MODEL.get('gpt-4o-mini'))
    input_cost = input_tokens * pricing['input']
    output_cost = output_tokens * pricing['output']
    return round(input_cost + output_cost, 6)


class TraceSpan:
    def __init__(
        self,
        name: str,
        trace_id: str | None = None,
        parent_span_id: str | None = None,
        attributes: dict[str, Any] | None = None,
    ) -> None:
        self.span_id: str = uuid.uuid4().hex[:12]
        self.trace_id: str = trace_id or uuid.uuid4().hex[:12]
        self.parent_span_id: str | None = parent_span_id
        self.name: str = name
        self.attributes: dict[str, Any] = attributes or {}
        self.start_time: datetime = datetime.now(timezone.utc)
        self.end_time: datetime | None = None
        self.status: str = 'ok'
        self.duration_ms: float = 0.0
        self.events: list[dict[str, Any]] = []

    def end(self, status: str = 'ok') -> None:
        self.end_time = datetime.now(timezone.utc)
        self.status = status
        self.duration_ms = (self.end_time - self.start_time).total_seconds() * 1000

    def add_event(self, name: str, attributes: dict[str, Any] | None = None) -> None:
        self.events.append({
            'name': name,
            'timestamp': datetime.now(timezone.utc).isoformat(),
            'attributes': attributes or {},
        })

    def record_llm_call(
        self,
        model: str,
        input_tokens: int,
        output_tokens: int,
        latency_ms: float,
        success: bool = True,
    ) -> None:
        cost = _estimate_cost(model, input_tokens, output_tokens)
        self.attributes.update({
            'llm.model': model,
            'llm.input_tokens': input_tokens,
            'llm.output_tokens': output_tokens,
            'llm.total_tokens': input_tokens + output_tokens,
            'llm.cost_usd': cost,
            'llm.latency_ms': round(latency_ms, 2),
        })
        self.add_event('llm.call', {
            'model': model,
            'input_tokens': input_tokens,
            'output_tokens': output_tokens,
            'cost_usd': cost,
            'latency_ms': round(latency_ms, 2),
            'success': success,
        })

    def to_dict(self) -> dict[str, Any]:
        return {
            'trace_id': self.trace_id,
            'span_id': self.span_id,
            'parent_span_id': self.parent_span_id,
            'name': self.name,
            'attributes': self.attributes,
            'events': self.events,
            'start_time': self.start_time.isoformat(),
            'end_time': self.end_time.isoformat() if self.end_time else None,
            'duration_ms': round(self.duration_ms, 2),
            'status': self.status,
        }


class Tracer:
    def __init__(self) -> None:
        self._spans: dict[str, list[TraceSpan]] = {}

    def start_span(self, name: str, attributes: dict[str, Any] | None = None, parent_span: TraceSpan | None = None) -> TraceSpan:
        span = TraceSpan(
            name=name,
            trace_id=parent_span.trace_id if parent_span else None,
            parent_span_id=parent_span.span_id if parent_span else None,
            attributes=attributes,
        )
        if span.trace_id not in self._spans:
            self._spans[span.trace_id] = []
        self._spans[span.trace_id].append(span)
        return span

    def end_span(self, span: TraceSpan, status: str = 'ok') -> None:
        span.end(status)

    def get_trace(self, trace_id: str) -> list[TraceSpan]:
        return self._spans.get(trace_id, [])

    def get_all_traces(self) -> dict[str, list[TraceSpan]]:
        return dict(self._spans)

    def get_all_spans(self) -> list[TraceSpan]:
        """Return all spans across all traces, newest first."""
        spans = [s for spans_list in self._spans.values() for s in spans_list]
        spans.sort(key=lambda s: s.start_time, reverse=True)
        return spans

    def search_spans(self, name: str | None = None, status: str | None = None) -> list[TraceSpan]:
        """Search spans by name or status."""
        spans = self.get_all_spans()
        if name:
            spans = [s for s in spans if name.lower() in s.name.lower()]
        if status:
            spans = [s for s in spans if s.status == status]
        return spans

    def get_trace_summary(self, trace_id: str) -> dict[str, Any]:
        spans = self.get_trace(trace_id)
        if not spans:
            return {}
        root = spans[0]
        total_cost = sum(s.attributes.get('llm.cost_usd', 0) or 0 for s in spans)
        total_tokens = sum(s.attributes.get('llm.total_tokens', 0) or 0 for s in spans)
        return {
            'trace_id': trace_id,
            'root_name': root.name,
            'span_count': len(spans),
            'total_duration_ms': root.duration_ms,
            'total_cost_usd': round(total_cost, 6),
            'total_tokens': total_tokens,
            'status': root.status,
            'start_time': root.start_time.isoformat(),
        }

    def export(self) -> list[dict[str, Any]]:
        return [s.to_dict() for s in self.get_all_spans()]


_tracer = Tracer()


def get_tracer() -> Tracer:
    return _tracer
