"""Pluggable web-search augmentation for the requirement analysis stage.

The requirement LLM stage can be enriched with real-world product / competitor
/ audience context gathered from a web-search provider.  The provider is
selected via ``SEARCH_PROVIDER`` in ``.env``:

* ``tavily``  — Tavily Search API (needs ``TAVILY_API_KEY``)
* anything else — :class:`NoOpSearchProvider` (degrades gracefully, no calls)

This keeps the pipeline fully functional even without an external search key;
callers just receive an empty context string and proceed as before.
"""
from __future__ import annotations

from dataclasses import dataclass
from typing import Any

from app.config import SEARCH_ENABLED, TAVILY_API_KEY, SEARCH_MAX_RESULTS, SEARCH_PROVIDER


@dataclass
class SearchResult:
    title: str
    url: str
    content: str


class BaseSearchProvider:
    name = "base"

    def search(self, query: str, max_results: int = SEARCH_MAX_RESULTS) -> list[SearchResult]:
        raise NotImplementedError


class NoOpSearchProvider(BaseSearchProvider):
    """Fallback provider: returns nothing, so the pipeline runs unchanged."""

    name = "none"

    def search(self, query: str, max_results: int = SEARCH_MAX_RESULTS) -> list[SearchResult]:
        return []


class TavilySearchProvider(BaseSearchProvider):
    name = "tavily"

    def __init__(self) -> None:
        import requests

        self._requests = requests

    def search(self, query: str, max_results: int = SEARCH_MAX_RESULTS) -> list[SearchResult]:
        if not TAVILY_API_KEY:
            return []
        try:
            resp = self._requests.post(
                "https://api.tavily.com/search",
                json={
                    "api_key": TAVILY_API_KEY,
                    "query": query,
                    "max_results": max_results,
                    "search_depth": "basic",
                },
                timeout=15,
            )
            resp.raise_for_status()
            data = resp.json()
            results: list[SearchResult] = []
            for r in data.get("results", []):
                results.append(
                    SearchResult(
                        title=r.get("title", ""),
                        url=r.get("url", ""),
                        content=r.get("content", ""),
                    )
                )
            return results
        except Exception as exc:  # network / auth errors must never break the pipeline
            print(f"  [Search] Tavily error: {exc}")
            return []


_PROVIDERS: dict[str, type[BaseSearchProvider]] = {
    "tavily": TavilySearchProvider,
    "none": NoOpSearchProvider,
}


def get_search_provider() -> BaseSearchProvider:
    cls = _PROVIDERS.get(SEARCH_PROVIDER, NoOpSearchProvider)
    try:
        return cls()
    except Exception:
        return NoOpSearchProvider()


def gather_requirement_context(
    product_name: str = "",
    brand: str = "",
    competitors: list[str] | None = None,
    target_audience: str = "",
    brief: str = "",
) -> str:
    """Run a few targeted searches and return concatenated context text.

    The text is meant to be appended to the requirement LLM user message so the
    model can ground its analysis in real product / competitor / audience info.
    Returns '' when search is disabled or yields nothing.
    """
    if not SEARCH_ENABLED:
        return ""

    queries: list[str] = []
    if product_name:
        queries.append(f"{product_name} 产品卖点 参数 官方介绍")
    if brand:
        queries.append(f"{brand} 品牌 广告 营销 案例")
    for comp in (competitors or [])[:2]:
        queries.append(f"{comp} 广告 竞品 分析")
    if target_audience:
        queries.append(f"{target_audience} 消费偏好 媒体习惯")
    # When we only have the raw brief, still try a generic reference query.
    if not queries and brief:
        queries.append(f"{brief[:60]} 产品 广告 参考")

    if not queries:
        return ""

    provider = get_search_provider()
    chunks: list[str] = []
    for q in queries[:4]:
        for r in provider.search(q):
            snippet = (r.content or "").strip().replace("\n", " ")
            if snippet:
                chunks.append(f"- {r.title} ({r.url}): {snippet[:300]}")

    if not chunks:
        return ""

    return "## 搜索补充信息（用于需求分析参考）\n" + "\n".join(chunks)
