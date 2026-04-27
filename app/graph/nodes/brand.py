from __future__ import annotations

import json

from langchain_core.messages import AIMessage
from pydantic import ValidationError

from app.brand.research import gather_brand_research
from app.brand.tool_agent import gather_brand_research_with_tools
from app.config import BRAND_RESEARCH_STRATEGY
from app.artifacts import resolve_artifact_run_id, write_artifact_json
from app.graph.state import AgentState
from app.llm import chat_with_structured_output
from app.schemas.brand import BrandProfile
from app.utils_messages import latest_human_text


_BRAND_SYSTEM = """你是品牌广告信息抽取助手。根据用户 brief 以及可选的「页面/检索摘录」，抽取结构化品牌档案。
规则：
- 以用户原文为主；摘录来自公开网页或检索摘要，可能片面、过期或错误，请交叉核对。
- 没有的信息留空字符串或空数组；不要编造 trust_signals。
- 摘录与用户原文冲突、或摘录来源可疑时，在 uncertain_fields 简短说明。
- 输出严格遵循结构化字段。"""


def node_extract_brand_profile(state: AgentState) -> dict:
    text = latest_human_text(state.get("messages"))
    if not text.strip():
        err = {"step": "brand", "message": "缺少用户 brief（messages 中无 human 内容）。"}
        return {"errors": (state.get("errors") or []) + [err]}

    stripped = text.strip()
    if stripped.startswith("{") and stripped.endswith("}"):
        try:
            data = json.loads(stripped)
            profile = BrandProfile.model_validate(data)
            summary = (
                f"已使用提供的结构化品牌档案：{profile.brand_name or profile.product_name or '未命名'}。"
            )
            rid, extra = resolve_artifact_run_id(state)  # type: ignore[arg-type]
            write_artifact_json(rid, "brand_profile.json", profile.model_dump())
            return {
                "brand_profile": profile.model_dump(),
                "messages": [AIMessage(content=summary)],
                **extra,
            }
        except (json.JSONDecodeError, ValidationError):
            pass

    strategy = BRAND_RESEARCH_STRATEGY
    if strategy in ("pipeline", "legacy", "auto"):
        research, research_notes = gather_brand_research(text)
    else:
        research, research_notes = gather_brand_research_with_tools(text)
    human_blocks = [text.strip()]
    if research:
        human_blocks.append("--- 页面/检索摘录（已清洗为纯文本） ---\n" + research)
    if research_notes:
        human_blocks.append(
            "--- 抓取/检索旁注 ---\n" + "\n".join(f"- {n}" for n in research_notes)
        )
    human_payload = "\n\n".join(human_blocks)

    llm = chat_with_structured_output(BrandProfile)
    try:
        profile = llm.invoke(
            [
                ("system", _BRAND_SYSTEM),
                ("human", human_payload),
            ]
        )
    except Exception as exc:  # noqa: BLE001
        err = {"step": "brand", "message": f"LLM 调用或解析失败：{exc}"}
        return {"errors": (state.get("errors") or []) + [err]}
    if profile is None:
        profile = BrandProfile(
            product_description=text.strip()[:4000],
            uncertain_fields=["模型结构化输出为空，已降级为仅使用用户 brief。"],
        )
        summary = "已用用户 brief 作为后备品牌档案（结构化输出为空）。"
    else:
        summary = f"已抽取品牌档案：{profile.brand_name or profile.product_name or '未命名'}。"

    rid, extra = resolve_artifact_run_id(state)  # type: ignore[arg-type]
    write_artifact_json(rid, "brand_profile.json", profile.model_dump())
    return {
        "brand_profile": profile.model_dump(),
        "messages": [AIMessage(content=summary)],
        **extra,
    }
