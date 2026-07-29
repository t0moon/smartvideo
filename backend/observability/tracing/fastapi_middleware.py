from __future__ import annotations

import time
from typing import Any

from fastapi import FastAPI, Request
from starlette.middleware.base import BaseHTTPMiddleware

from observability.tracing import get_tracer
from observability.metrics import get_metrics


class TracingMiddleware(BaseHTTPMiddleware):
    """FastAPI middleware that traces every HTTP request as a span."""

    def __init__(self, app: FastAPI) -> None:
        super().__init__(app)

    async def dispatch(self, request: Request, call_next: Any) -> Any:
        tracer = get_tracer()
        metrics = get_metrics()

        span_name = f'{request.method} {request.url.path}'
        span = tracer.start_span(span_name, attributes={
            'http.method': request.method,
            'http.path': request.url.path,
            'http.host': request.url.hostname or '',
            'http.query': str(request.url.query),
        })

        start = time.perf_counter()
        try:
            response = await call_next(request)
            status = response.status_code
            tracer.end_span(span, 'ok' if status < 500 else 'error')
            span.attributes['http.status_code'] = status
            return response
        except Exception as exc:
            tracer.end_span(span, 'error')
            span.attributes['error'] = str(exc)
            metrics.increment('http.error', {'path': request.url.path})
            raise
        finally:
            elapsed = (time.perf_counter() - start) * 1000
            span.attributes['duration_ms'] = round(elapsed, 2)
            metrics.timing('http.request_duration', elapsed, {
                'method': request.method,
                'path': request.url.path,
            })
            metrics.increment('http.request', {'method': request.method})


def add_tracing_middleware(app: FastAPI) -> None:
    """Register the tracing middleware on a FastAPI app."""
    app.add_middleware(TracingMiddleware)
