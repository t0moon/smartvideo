"""品牌调研：模型 bind_tools → 执行工具 → 将 ToolMessage 回传模型，多轮直至不再调用工具。"""

from __future__ import annotations

import json
import os
from typing import Any

from langchain_core.messages import AIMessage, HumanMessage, SystemMessage, ToolMessage

from app.brand.research import _env_flag, _WEB_DEFAULT
from app.brand.research_tools import BRAND_RESEARCH_TOOLS
from app.config import BRAND_TOOL_AGENT_MAX_ROUNDS
from app.llm import get_chat_model

_MAX_CONTEXT_CHARS = 12_000


def _tool_args(raw: Any) -> dict[str, Any]:
    if isinstance(raw, dict):
        return raw
    if isinstance(raw, str) and raw.strip():
        try:
            return json.loads(raw)
        except json.JSONDecodeError:
            return {}
    return {}


def _call_name_id_args(call: Any) -> tuple[str, str, dict[str, Any]]:
    if isinstance(call, dict):
        return (
            str(call.get("name") or ""),
            str(call.get("id") or ""),
            _tool_args(call.get("args")),
        )
    name = str(getattr(call, "name", "") or "")
    cid = str(getattr(call, "id", "") or "")
    return name, cid, _tool_args(getattr(call, "args", None))


_TOOL_AGENT_SYSTEM = """你是品牌广告调研助手。用户会提供产品/品牌的 brief（可能含链接、也可能只有描述）。
你的任务：通过工具收集**可核对**的公开信息片段，供下一步「结构化品牌档案」抽取使用。

可用工具：
- fetch_web_page：当用户给出或可推断出具体 http(s) 页面时使用。
- search_web：当需要补充行业、竞品、品牌公开信息时使用；查询词用 brief 中的品牌名/产品名/品类等，勿编造实体。

原则：
- 先读 brief，再决定调用哪个工具；可多次调用。
- 工具返回可能片面或过期，不要自行捏造事实；失败时换关键词或换 URL 再试。
- 当已足够支撑下游抽取（或工具多次失败）时，**停止调用工具**，用 2～4 句中文简要概括你收集到的要点与缺口（无新工具调用）。"""


def gather_brand_research_with_tools(user_brief: str) -> tuple[str, list[str]]:
    """使用与抽取节点相同的 ChatOpenAI（OPENAI_API_KEY / OPENAI_BASE_URL / OPENAI_MODEL）做多轮 tool 调用。"""
    notes: list[str] = []
    if not _env_flag("BRAND_WEB_RESEARCH", _WEB_DEFAULT):
        return "", notes

    llm = get_chat_model().bind_tools(BRAND_RESEARCH_TOOLS)
    by_name = {t.name: t for t in BRAND_RESEARCH_TOOLS}

    messages = [
        SystemMessage(content=_TOOL_AGENT_SYSTEM),
        HumanMessage(content=user_brief.strip()),
    ]

    transcript_parts: list[str] = []
    max_rounds = max(1, BRAND_TOOL_AGENT_MAX_ROUNDS)

    for _ in range(max_rounds):
        ai = llm.invoke(messages)
        if not isinstance(ai, AIMessage):
            notes.append("模型返回非 AIMessage，已中止调研轮次。")
            break
        messages.append(ai)

        calls = ai.tool_calls or []
        if not calls:
            if ai.content:
                transcript_parts.append(f"--- 调研助手总结 ---\n{str(ai.content).strip()}")
            break

        for idx, call in enumerate(calls):
            name, raw_id, args = _call_name_id_args(call)
            if not raw_id:
                raw_id = f"tool_call_{idx}"
            tool_fn = by_name.get(name)
            header = f"### tool:{name} args={args!r}"
            if tool_fn is None:
                body = f"[错误] 未知工具：{name}"
            else:
                try:
                    body = tool_fn.invoke(args)
                except Exception as exc:  # noqa: BLE001
                    body = f"[错误] 工具执行失败：{exc}"
                    notes.append(str(exc))
            transcript_parts.append(f"{header}\n{body}")
            cap = int(os.getenv("BRAND_TOOL_MESSAGE_MAX_CHARS") or "16000")
            safe_body = body if len(body) <= cap else body[:cap] + "\n…（回传模型前已截断）"
            messages.append(ToolMessage(content=safe_body, tool_call_id=raw_id))
    else:
        notes.append(f"品牌工具调研达到轮次上限 {max_rounds}，已停止。")

    raw = "\n\n".join(transcript_parts).strip()
    if len(raw) > _MAX_CONTEXT_CHARS:
        raw = raw[:_MAX_CONTEXT_CHARS] + "\n…（摘录总长度已截断）"
        notes.append("摘录总长度已截断至配置上限。")

    return raw, notes
