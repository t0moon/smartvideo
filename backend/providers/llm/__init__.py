from __future__ import annotations

from .base import BaseLLMProvider
from .openai_provider import OpenAIProvider
from .mock_provider import MockLLMProvider
from .deepseek_provider import DeepSeekProvider
from app.config import LLM_PROVIDER, OPENAI_API_KEY


def get_llm_provider() -> BaseLLMProvider:
    # Explicit provider selection takes priority (so DeepSeek works even when
    # OPENAI_API_KEY is empty — otherwise the mock fallback would wrongly win).
    if LLM_PROVIDER == 'deepseek':
        return DeepSeekProvider()
    if LLM_PROVIDER == 'mock':
        return MockLLMProvider()
    if LLM_PROVIDER == 'openai':
        if not OPENAI_API_KEY:
            print('  [LLM] OPENAI_API_KEY not set — using MockLLMProvider')
            return MockLLMProvider()
        return OpenAIProvider()
    # default: openai if key present, else mock
    if OPENAI_API_KEY:
        return OpenAIProvider()
    print('  [LLM] OPENAI_API_KEY not set — using MockLLMProvider')
    return MockLLMProvider()
