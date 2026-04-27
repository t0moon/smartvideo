"""品牌调研用 LangChain tools（由模型选择调用，底层复用 research 实现）。"""

from __future__ import annotations

from langchain_core.tools import tool

from app.brand.research import fetch_public_page_text, search_public_web

_MAX_TOOL_CHARS = 14_000


@tool
def fetch_web_page(url: str) -> str:
    """抓取单个公开网页，返回清洗后的纯文本（HTML 会去掉脚本/样式）。仅传入 http 或 https 完整 URL。"""
    raw = fetch_public_page_text(url)
    if len(raw) > _MAX_TOOL_CHARS:
        return raw[:_MAX_TOOL_CHARS] + "\n…（工具输出已截断）"
    return raw


@tool
def search_web(query: str) -> str:
    """用关键词做公开网页检索，返回标题/链接/摘要列表（DuckDuckGo）。用于补充 brief 中未给链接时的背景信息。"""
    raw = search_public_web(query)
    if len(raw) > _MAX_TOOL_CHARS:
        return raw[:_MAX_TOOL_CHARS] + "\n…（工具输出已截断）"
    return raw


BRAND_RESEARCH_TOOLS = [fetch_web_page, search_web]
