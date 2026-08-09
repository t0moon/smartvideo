from __future__ import annotations

import time
from pathlib import Path
from typing import Any

from pydantic import BaseModel
from models.factory import ModelRouter
from shared.schemas import BrandProfile, VideoSpec, Storyboard, Scene, Shot, ProjectStage
from observability.tracing import get_tracer
from observability.metrics import get_metrics


# Lazy import — skills/ is optional; if missing, injection is a no-op.
def _get_skill_prompt(stage_name: str) -> str:
    try:
        from skills.loader import get_skill_prompt as _gsp
        return _gsp(stage_name)
    except Exception:
        return ""


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

    def _build_system(self, stage_name: str) -> str:
        """Return the complete system prompt for *stage_name*.

        Each SKILL.md is a self-contained system prompt (role + methodology +
        rules + examples).  The loader matches *stage_name* to the right
        SKILL.md body; base prompts in `agents/prompts/` serve as fallback
        only when no skill matches the stage.
        """
        skill_text = _get_skill_prompt(stage_name)
        if skill_text:
            return skill_text.strip()
        return self._load_prompt(stage_name)

    def understand_requirement(self, brief: str, search_context: str = '',
                                previous_spec: VideoSpec | None = None) -> VideoSpec:
        system = self._build_system('requirement')
        if not system:
            system = 'Extract video specification from the user brief. Return a JSON object.'
        messages: list[dict] = [{'role': 'system', 'content': system}]
        user_content = brief
        if search_context:
            user_content += '\n\n' + search_context
        messages.append({'role': 'user', 'content': user_content})

        # Multi-turn: if the user rejected with feedback, show the LLM its
        # previous output so it can do a targeted revision.
        if previous_spec is not None:
            try:
                prev_json = previous_spec.model_dump_json(indent=2)
            except Exception:
                prev_json = str(previous_spec)
            messages.append({'role': 'assistant', 'content': prev_json})
            # The feedback text is already part of search_context as the
            # second user message; no extra user message needed here.
            # (callers: workflow._exec_requirement passes feedback through
            #  the search_context chain for now; we keep the signature ready.)

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

    def generate_storyboard(self, spec: VideoSpec, brand: BrandProfile | None = None,
                            feedback: str = '', previous_storyboard: Storyboard | None = None) -> Storyboard:
        system = self._build_system('storyboard')
        if not system:
            system = 'Generate a storyboard from the video specification.'
        context = f'Video Spec:\n{spec.model_dump_json(indent=2)}\n'
        if brand:
            context += f'\nBrand Profile:\n{brand.model_dump_json(indent=2)}'
        messages: list[dict] = [
            {'role': 'system', 'content': system},
            {'role': 'user', 'content': context},
        ]
        # Multi-turn: show previous output so LLM can target edits.
        if previous_storyboard is not None:
            try:
                prev_json = previous_storyboard.model_dump_json(indent=2)
            except Exception:
                prev_json = str(previous_storyboard)
            messages.append({'role': 'assistant', 'content': prev_json})
        # User feedback as a follow-up message (revision round).
        if feedback:
            messages.append({
                'role': 'user',
                'content': f'## 用户修改意见（请据此修订，保留用户认可的部分，仅修改被指出的问题）\n{feedback}',
            })
        start = time.perf_counter()
        try:
            result = self.router.chat_structured(messages, Storyboard)
            elapsed = (time.perf_counter() - start) * 1000
            _trace_llm_call('chat_structured', messages, result, 'llm.generate_storyboard')
            return result if isinstance(result, Storyboard) else Storyboard()
        except Exception as exc:
            get_metrics().increment('llm.error', {'method': 'generate_storyboard'})
            return Storyboard()

    def generate_scenes(self, storyboard: Storyboard, brand: BrandProfile | None = None,
                         feedback: str = '', previous_scenes: list[Scene] | None = None) -> list[Scene]:
        system = self._build_system('scene')
        if not system:
            system = 'Generate detailed scene descriptions from the storyboard.'
        context = f'Storyboard:\n{storyboard.model_dump_json(indent=2)}\n'
        if brand:
            context += f'\nBrand:\n{brand.model_dump_json(indent=2)}'
        messages: list[dict] = [
            {'role': 'system', 'content': system},
            {'role': 'user', 'content': context},
        ]
        if previous_scenes:
            try:
                import json
                prev_json = json.dumps([s.model_dump() for s in previous_scenes], indent=2, ensure_ascii=False)
            except Exception:
                prev_json = str(previous_scenes)
            messages.append({'role': 'assistant', 'content': prev_json})
        if feedback:
            messages.append({
                'role': 'user',
                'content': f'## 用户修改意见（请据此调整场景/镜头设计）\n{feedback}',
            })
        start = time.perf_counter()
        try:
            result = self.router.chat_structured(messages, SceneList)
            elapsed = (time.perf_counter() - start) * 1000
            _trace_llm_call('chat_structured', messages, result, 'llm.generate_scenes')
            return result.scenes if hasattr(result, 'scenes') else []
        except Exception as exc:
            get_metrics().increment('llm.error', {'method': 'generate_scenes'})
            return []
