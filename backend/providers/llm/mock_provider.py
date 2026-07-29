from __future__ import annotations

"""Mock LLM provider — deterministic outputs when no OPENAI_API_KEY is set.

Lets the full pipeline (requirement -> storyboard -> scenes -> video) run
end-to-end without a real LLM. Generates a minimal 1-scene storyboard from
the raw brief so that downstream video generation (e.g. Kling) still works.
"""

from typing import Any

from .base import BaseLLMProvider


class MockLLMProvider(BaseLLMProvider):
    name = 'mock'

    def chat(self, messages: list[dict], **kwargs) -> str:
        user_text = self._last_user_text(messages)
        return f'[mock] {user_text[:200]}'

    def chat_structured(self, messages: list[dict], response_model: type, **kwargs) -> object:
        from shared.schemas import VideoSpec, Storyboard, Scene

        user_text = self._last_user_text(messages)
        model_name = getattr(response_model, '__name__', '')

        if model_name == 'VideoSpec':
            return VideoSpec(
                duration_sec=5,
                style='product ad, clean, modern',
                platform='web',
                voice_over=user_text[:100],
                subtitle_enabled=True,
                raw_brief=user_text,
            )

        if model_name == 'Storyboard':
            brief = self._extract_brief(user_text)
            scene = Scene(
                scene_id='scene_1',
                title='主画面',
                description=brief[:200] or 'Product showcase scene',
                duration_sec=5,
                prompt=brief[:300] or 'A cinematic product showcase, clean modern style',
            )
            return Storyboard(
                storyboard_id='sb_mock',
                scenes=[scene],
                style_notes='mock storyboard (no LLM key configured)',
                total_duration_sec=5,
            )

        # SceneList or anything with a `scenes` field
        if hasattr(response_model, 'model_fields') and 'scenes' in response_model.model_fields:
            brief = self._extract_brief(user_text)
            scene = Scene(
                scene_id='scene_1',
                title='主画面',
                description=brief[:200] or 'Product showcase scene',
                duration_sec=5,
                prompt=brief[:300] or 'A cinematic product showcase, clean modern style',
            )
            try:
                return response_model(scenes=[scene])
            except Exception:
                return response_model()

        try:
            return response_model()
        except Exception:
            return None

    # ── helpers ──────────────────────────────────────────────────────────

    @staticmethod
    def _last_user_text(messages: list[dict]) -> str:
        for m in reversed(messages):
            if m.get('role') == 'user' and isinstance(m.get('content'), str):
                return m['content']
        return ''

    @staticmethod
    def _extract_brief(text: str) -> str:
        """Pull raw_brief / description out of a JSON-ish context blob if present."""
        import json
        import re

        m = re.search(r'"raw_brief"\s*:\s*"([^"]+)"', text)
        if m:
            return m.group(1)
        m = re.search(r'"description"\s*:\s*"([^"]+)"', text)
        if m:
            return m.group(1)
        try:
            data: Any = json.loads(text)
            if isinstance(data, dict):
                return str(data.get('raw_brief') or data.get('description') or text)
        except Exception:
            pass
        return text
