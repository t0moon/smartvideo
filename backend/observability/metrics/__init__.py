from __future__ import annotations

import time
from datetime import datetime, timezone
from typing import Any


class MetricsCollector:
    def __init__(self) -> None:
        self._counters: dict[str, int] = {}
        self._gauges: dict[str, float] = {}
        self._timings: dict[str, list[float]] = {}
        self._histograms: dict[str, list[float]] = {}

    def increment(self, name: str, tags: dict[str, str] | None = None, value: int = 1) -> None:
        key = self._key(name, tags)
        self._counters[key] = self._counters.get(key, 0) + value

    def gauge(self, name: str, value: float, tags: dict[str, str] | None = None) -> None:
        key = self._key(name, tags)
        self._gauges[key] = value

    def timing(self, name: str, duration_ms: float, tags: dict[str, str] | None = None) -> None:
        key = self._key(name, tags)
        if key not in self._timings:
            self._timings[key] = []
        self._timings[key].append(duration_ms)

    def histogram(self, name: str, value: float, tags: dict[str, str] | None = None) -> None:
        """Record a histogram observation (e.g. token counts, costs)."""
        key = self._key(name, tags)
        if key not in self._histograms:
            self._histograms[key] = []
        self._histograms[key].append(value)

    def record_llm_usage(self, model: str, input_tokens: int, output_tokens: int, cost_usd: float) -> None:
        self.increment('llm.call_count', {'model': model})
        self.histogram('llm.input_tokens', input_tokens, {'model': model})
        self.histogram('llm.output_tokens', output_tokens, {'model': model})
        self.histogram('llm.cost_usd', cost_usd, {'model': model})
        self.increment('llm.total_tokens', {'model': model}, value=input_tokens + output_tokens)

    def get_counter(self, name: str, tags: dict[str, str] | None = None) -> int:
        return self._counters.get(self._key(name, tags), 0)

    def snapshot(self) -> dict[str, Any]:
        def stats(vals: list[float]) -> dict[str, float]:
            if not vals:
                return {'count': 0, 'sum': 0, 'avg': 0, 'max': 0, 'min': 0}
            return {
                'count': len(vals),
                'sum': round(sum(vals), 2),
                'avg': round(sum(vals) / len(vals), 2),
                'max': round(max(vals), 2),
                'min': round(min(vals), 2),
            }

        return {
            'timestamp': datetime.now(timezone.utc).isoformat(),
            'counters': dict(self._counters),
            'gauges': dict(self._gauges),
            'timings': {k: stats(v) for k, v in self._timings.items()},
            'histograms': {k: stats(v) for k, v in self._histograms.items()},
        }

    def reset(self) -> None:
        self._counters.clear()
        self._gauges.clear()
        self._timings.clear()
        self._histograms.clear()

    def _key(self, name: str, tags: dict[str, str] | None) -> str:
        if not tags:
            return name
        tag_str = ','.join(f'{k}={v}' for k, v in sorted(tags.items()))
        return f'{name}[{tag_str}]'


_metrics = MetricsCollector()


def get_metrics() -> MetricsCollector:
    return _metrics
