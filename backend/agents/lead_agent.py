from __future__ import annotations

import time
from pathlib import Path
from typing import Any

from pydantic import BaseModel
from models.factory import ModelRouter
from shared.schemas import BrandProfile, VideoSpec, Storyboard, Scene, Shot, ProjectStage
from observability.tracing import get_tracer
from observability.metrics import get_metrics


class SceneList(BaseModel):
    scenes: list[Scene] = []


def _estimate_tokens(text: str) -> int:
    """Rough token estimate: ~4 chars per token."""
    return max(1, len(text) // 4)


def _trace_llm_call(method: str, messages: list[dict], result: Any, span_name: str) -> None:
    """Record an LLM call as a span with cost estimation."""
    tracer = get_tracer()
    metrics = get_metrics()

    input_text = ' '.join(m.get('content', '') or '' for m in messages if isinstance(m.get('content'), str))
    input_tokens = _estimate_tokens(input_text)
    output_text = str(result) if isinstance(result, str) else (result.model_dump_json() if isinstance(result, BaseModel) else str(result))
    output_tokens = _estimate_tokens(output_text)

    span = tracer.start_span(span_name, attributes={
        'method': method,
        'model': 'gpt-4o-mini',
        'input_tokens_est': input_tokens,
        'output_tokens_est': output_tokens,
    })
    span.record_llm_call('gpt-4o-mini', input_tokens, output_tokens, 0)
    tracer.end_span(span, 'ok')

    metrics.record_llm_usage('gpt-4o-mini', input_tokens, output_tokens,
                              span.attributes.get('llm.cost_usd', 0))


class LeadAgent:
    def __init__(self) -> None:
        self.router = ModelRouter()

    def _load_prompt(self, name: str) -> str:
        path = Path(__file__).parent / 'prompts' / f'{name}.txt'
        if path.exists():
            return path.read_text(encoding='utf-8')
        return ''

    def understand_requirement(self, brief: str) -> VideoSpec:
        system = self._load_prompt('requirement')
        if not system:
            system = 'Extract video specification from the user brief. Return a JSON object.'
        messages = [
            {'role': 'system', 'content': system},
            {'role': 'user', 'content': brief},
        ]
        start = time.perf_counter()
        try:
            result = self.router.chat_structured(messages, VideoSpec)
            elapsed = (time.perf_counter() - start) * 1000
            _trace_llm_call('chat_structured', messages, result, 'llm.understand_requirement')
            if isinstance(result, VideoSpec):
                result.raw_brief = brief
                return result
            return VideoSpec(raw_brief=brief)
        except Exception as exc:
            elapsed = (time.perf_counter() - start) * 1000
            get_tracer().start_span('llm.understand_requirement.error', attributes={'error': str(exc)})
            get_metrics().increment('llm.error', {'method': 'understand_requirement'})
            return VideoSpec(raw_brief=brief)

    def generate_storyboard(self, spec: VideoSpec, brand: BrandProfile | None = None) -> Storyboard:
        system = self._load_prompt('storyboard')
        if not system:
            system = 'Generate a storyboard from the video specification.'
        context = f'Video Spec:\n{spec.model_dump_json(indent=2)}\n'
        if brand:
            context += f'\nBrand Profile:\n{brand.model_dump_json(indent=2)}'
        messages = [
            {'role': 'system', 'content': system},
            {'role': 'user', 'content': context},
        ]
        start = time.perf_counter()
        try:
            result = self.router.chat_structured(messages, Storyboard)
            elapsed = (time.perf_counter() - start) * 1000
            _trace_llm_call('chat_structured', messages, result, 'llm.generate_storyboard')
            return result if isinstance(result, Storyboard) else Storyboard()
        except Exception as exc:
            get_metrics().increment('llm.error', {'method': 'generate_storyboard'})
            return Storyboard()

    def generate_scenes(self, storyboard: Storyboard, brand: BrandProfile | None = None) -> list[Scene]:
        system = self._load_prompt('scene')
        if not system:
            system = 'Generate detailed scene descriptions from the storyboard.'
        context = f'Storyboard:\n{storyboard.model_dump_json(indent=2)}\n'
        if brand:
            context += f'\nBrand:\n{brand.model_dump_json(indent=2)}'
        messages = [
            {'role': 'system', 'content': system},
            {'role': 'user', 'content': context},
        ]
        start = time.perf_counter()
        try:
            result = self.router.chat_structured(messages, SceneList)
            elapsed = (time.perf_counter() - start) * 1000
            _trace_llm_call('chat_structured', messages, result, 'llm.generate_scenes')
            return result.scenes if hasattr(result, 'scenes') else []
        except Exception as exc:
            get_metrics().increment('llm.error', {'method': 'generate_scenes'})
            return []
