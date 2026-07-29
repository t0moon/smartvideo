from __future__ import annotations

"""DeepSeek LLM provider.

DeepSeek's chat API is OpenAI-compatible, but it does NOT support the
``json_schema`` response_format that the OpenAI provider relies on
(returns 400 "This response_format type is unavailable now"). It does support
``json_object`` mode, so we emit the Pydantic schema into a system prompt and
parse the JSON response back into the target model.
"""

# Langfuse-patched OpenAI client (keeps LLM calls auto-traced)
from langfuse.openai import openai

from .base import BaseLLMProvider
from app.config import DEEPSEEK_API_KEY, DEEPSEEK_BASE_URL, DEEPSEEK_MODEL


class DeepSeekProvider(BaseLLMProvider):
    name = 'deepseek'

    def __init__(self) -> None:
        self.model = DEEPSEEK_MODEL
        self.api_key = DEEPSEEK_API_KEY
        self.base_url = DEEPSEEK_BASE_URL

    def _get_client(self):
        kwargs = {'api_key': self.api_key, 'base_url': self.base_url}
        return openai.OpenAI(**kwargs)

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

        system_prompt = (
            "You are a helpful assistant that outputs JSON only. "
            "Return a single JSON object that strictly conforms to this JSON Schema. "
            "Do not include any explanation, commentary, or markdown code fences.\n\n"
            "Hard rules:\n"
            "- Fill EVERY field with a concrete, meaningful value. Never leave a string field empty.\n"
            "- For text fields, write natural-language content in the same language as the user's request.\n"
            "- If a field is not explicitly stated in the request, infer a sensible default — do not omit it.\n\n"
            f"Schema:\n{json.dumps(schema, ensure_ascii=False, indent=2)}"
        )
        full_messages = [{'role': 'system', 'content': system_prompt}] + list(messages)

        last_err = None
        for attempt in range(2):
            try:
                response = client.chat.completions.create(
                    model=kwargs.get('model', self.model),
                    messages=full_messages,
                    response_format={'type': 'json_object'},
                    temperature=kwargs.get('temperature', 0.7),
                )
                raw = response.choices[0].message.content or '{}'
                data = json.loads(self._strip_fences(raw))
                return response_model.model_validate(data)
            except (json.JSONDecodeError, ValidationError) as exc:
                last_err = exc
                # Retry once with a stricter reminder appended
                full_messages = full_messages + [
                    {'role': 'user', 'content': 'Your previous output was not valid JSON. '
                                                 'Output ONLY the JSON object, no other text.'}
                ]
        # Final fallback: return an empty (default) instance so the pipeline continues
        print(f'  [DeepSeek] chat_structured failed ({last_err}); returning default {response_model.__name__}')
        try:
            return response_model()
        except Exception:
            return None

    @staticmethod
    def _strip_fences(text: str) -> str:
        """Remove ```json ... ``` fences if the model wrapped the JSON anyway."""
        t = text.strip()
        if t.startswith('```'):
            # drop first line (```json) and trailing ```
            t = t.split('\n', 1)[1] if '\n' in t else t[3:]
            if t.endswith('```'):
                t = t[:-3]
            t = t.strip()
        return t
