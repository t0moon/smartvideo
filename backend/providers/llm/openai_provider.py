from __future__ import annotations

"""Langfuse OpenAI integration: auto-instruments all OpenAI calls.

This module replaces the standard openai import with Langfuse's patched version.
Langfuse must be imported AFTER environment variables are loaded (done in app.config).
"""

# Import Langfuse-patched OpenAI *before* creating any client
# This hooks into the OpenTelemetry context for auto-nesting
from langfuse.openai import openai

from .base import BaseLLMProvider
from app.config import OPENAI_API_KEY, OPENAI_BASE_URL, OPENAI_MODEL


# Re-export the patched OpenAI class
_PatchedOpenAI = openai.OpenAI


class OpenAIProvider(BaseLLMProvider):
    name = 'openai'

    def __init__(self) -> None:
        self.model = OPENAI_MODEL
        self.api_key = OPENAI_API_KEY
        self.base_url = OPENAI_BASE_URL

    def _get_client(self):
        kwargs = {'api_key': self.api_key}
        if self.base_url:
            kwargs['base_url'] = self.base_url
        # Uses Langfuse-patched OpenAI client for automatic tracing
        return _PatchedOpenAI(**kwargs)

    def chat(self, messages: list[dict], **kwargs) -> str:
        client = self._get_client()
        response = client.chat.completions.create(
            model=kwargs.get('model', self.model),
            messages=messages,
            temperature=kwargs.get('temperature', 0.7),
        )
        return response.choices[0].message.content or ''

    def chat_structured(self, messages: list[dict], response_model: type, **kwargs) -> object:
        import json
        from pydantic import ValidationError

        client = self._get_client()
        schema = response_model.model_json_schema()
        response = client.chat.completions.create(
            model=kwargs.get('model', self.model),
            messages=messages,
            response_format={
                'type': 'json_schema',
                'json_schema': {
                    'name': response_model.__name__,
                    'schema': schema,
                },
            },
            temperature=kwargs.get('temperature', 0.7),
        )
        raw = response.choices[0].message.content or '{}'
        try:
            data = json.loads(raw)
            return response_model.model_validate(data)
        except (json.JSONDecodeError, ValidationError):
            return response_model()
