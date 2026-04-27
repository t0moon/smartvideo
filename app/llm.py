import os
import re
from typing import Any

from langchain_core.messages import AIMessage, HumanMessage
from langchain_openai import ChatOpenAI
from pydantic import BaseModel

from app.config import OPENAI_BASE_URL, OPENAI_MODEL

# gpt-5 等模型在部分网关下原生 structured parse 可能返回 parsed=None，
# 默认改用 function_calling；可用环境变量 OPENAI_STRUCTURED_OUTPUT_METHOD 覆盖。
_STRUCTURED_METHOD = (os.getenv("OPENAI_STRUCTURED_OUTPUT_METHOD") or "function_calling").strip()

_FALLBACK_JSON_ONLY = HumanMessage(
    content=(
        "请仅输出一个 UTF-8 JSON 对象（字段需符合约定的结构化 schema），"
        "不要使用 Markdown 围栏，不要在 JSON 之外输出任何字符。"
    )
)


def _text_from_ai_message_content(content: Any) -> str:
    if isinstance(content, str):
        return content
    if isinstance(content, list):
        parts: list[str] = []
        for part in content:
            if isinstance(part, str):
                parts.append(part)
            elif isinstance(part, dict) and part.get("type") == "text":
                parts.append(str(part.get("text", "")))
        return "".join(parts)
    return str(content)


def _extract_json_object(text: str) -> str | None:
    raw = text.strip()
    fenced = re.search(r"```(?:json)?\s*\n?([\s\S]*?)```", raw, re.IGNORECASE)
    if fenced:
        raw = fenced.group(1).strip()
    start = raw.find("{")
    end = raw.rfind("}")
    if start == -1 or end <= start:
        return None
    return raw[start : end + 1]


def get_chat_model() -> ChatOpenAI:
    kwargs: dict = {"model": OPENAI_MODEL, "temperature": 0.2}
    if OPENAI_BASE_URL:
        kwargs["base_url"] = OPENAI_BASE_URL
    return ChatOpenAI(**kwargs)


class _StructuredWithJsonFallback:
    """兼容 OpenAI 兼容网关：with_structured_output 有时解析得到 None，再走一轮纯文本 JSON。"""

    def __init__(
        self,
        base_llm: ChatOpenAI,
        structured_runnable: Any,
        schema: type[BaseModel],
    ) -> None:
        self._llm = base_llm
        self._structured = structured_runnable
        self._schema = schema

    def invoke(self, input: Any, config: Any | None = None, **kwargs: Any) -> Any:
        out = self._structured.invoke(input, config=config, **kwargs)
        if out is not None:
            return out
        messages = list(input) if isinstance(input, list) else [input]
        raw_msg = self._llm.invoke(messages + [_FALLBACK_JSON_ONLY], config=config, **kwargs)
        if isinstance(raw_msg, AIMessage):
            content = raw_msg.content
        else:
            content = getattr(raw_msg, "content", raw_msg)
        text = _text_from_ai_message_content(content)
        blob = _extract_json_object(text)
        if blob:
            try:
                return self._schema.model_validate_json(blob)
            except Exception:
                pass
        return None


def chat_with_structured_output(schema: type[BaseModel]) -> Any:
    llm = get_chat_model()
    if _STRUCTURED_METHOD:
        structured = llm.with_structured_output(schema, method=_STRUCTURED_METHOD)  # type: ignore[arg-type]
    else:
        structured = llm.with_structured_output(schema)
    return _StructuredWithJsonFallback(llm, structured, schema)
