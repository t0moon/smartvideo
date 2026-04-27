from __future__ import annotations

import os
import re
from urllib.parse import urlparse

import httpx
from bs4 import BeautifulSoup

# 与图其他节点并行开发时，可用环境变量关闭联网（CI / 离线）。
_WEB_DEFAULT = "1"
_MAX_FETCH_BYTES = 2_000_000
_MAX_CONTEXT_CHARS = 12_000
_MAX_URLS = 5
_SEARCH_RESULTS = 6
_HTTP_TIMEOUT = 20.0

_HTTP_HEADERS = {
    "User-Agent": (
        "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
        "AppleWebKit/537.36 (KHTML, like Gecko) "
        "Chrome/123.0.0.0 Safari/537.36"
    ),
    "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8",
    "Accept-Language": "zh-CN,zh;q=0.9,en;q=0.8",
}

_URL_RE = re.compile(r"https?://[^\s\]>\"')]+", re.IGNORECASE)


def _env_flag(name: str, default: str) -> bool:
    return (os.getenv(name) or default).strip().lower() in {"1", "true", "yes", "on"}


def extract_urls(text: str) -> list[str]:
    seen: set[str] = set()
    out: list[str] = []
    for m in _URL_RE.finditer(text or ""):
        u = m.group(0).rstrip(").,;]}\"'")
        if u in seen:
            continue
        try:
            parsed = urlparse(u)
        except ValueError:
            continue
        if parsed.scheme not in {"http", "https"} or not parsed.netloc:
            continue
        seen.add(u)
        out.append(u)
        if len(out) >= _MAX_URLS:
            break
    return out


def _html_to_text(html: str) -> str:
    soup = BeautifulSoup(html, "html.parser")
    for tag in soup(["script", "style", "noscript", "template"]):
        tag.decompose()
    text = soup.get_text("\n", strip=True)
    lines = [ln for ln in (ln.strip() for ln in text.splitlines()) if ln]
    return "\n".join(lines)


def _fetch_url(client: httpx.Client, url: str) -> tuple[str, str | None]:
    try:
        resp = client.get(url, follow_redirects=True)
        resp.raise_for_status()
    except Exception as exc:  # noqa: BLE001 — 聚合任意网络错误
        return "", f"{url} 请求失败：{exc}"

    body = resp.content
    if len(body) > _MAX_FETCH_BYTES:
        body = body[:_MAX_FETCH_BYTES]

    ctype = (resp.headers.get("content-type") or "").lower()
    if "html" not in ctype and not url.lower().endswith((".htm", ".html")):
        try:
            snippet = body.decode(resp.encoding or "utf-8", errors="ignore")
        except Exception:
            snippet = ""
        snippet = snippet.strip()
        if len(snippet) > 8000:
            snippet = snippet[:8000] + "\n…（已截断）"
        label = url
        return f"[非 HTML 资源 {label}]\n{snippet}", None

    try:
        html = body.decode(resp.encoding or "utf-8", errors="ignore")
    except Exception as exc:
        return "", f"{url} 解码失败：{exc}"

    plain = _html_to_text(html)
    if len(plain) > 8000:
        plain = plain[:8000] + "\n…（已截断）"
    header = f"### 页面摘录：{url}\n"
    return header + plain, None


def _search_duckduckgo(query: str) -> tuple[str, str | None]:
    try:
        from ddgs import DDGS
    except ImportError:
        try:
            from duckduckgo_search import DDGS  # type: ignore[no-redef]
        except ImportError:
            return "", "未安装 ddgs（或 duckduckgo-search），跳过网页搜索。"

    q = (query or "").strip()
    if not q:
        return "", None

    lines: list[str] = []
    try:
        with DDGS() as ddgs:
            for i, item in enumerate(ddgs.text(q, max_results=_SEARCH_RESULTS), start=1):
                title = (item.get("title") or "").strip()
                href = (item.get("href") or "").strip()
                body = (item.get("body") or "").strip()
                chunk = " | ".join(p for p in (title, href, body) if p)
                if chunk:
                    lines.append(f"{i}. {chunk}")
    except Exception as exc:  # noqa: BLE001
        return "", f"DuckDuckGo 搜索失败：{exc}"

    if not lines:
        return "", None
    return "### 公开检索摘要（DuckDuckGo）\n" + "\n".join(lines), None


def fetch_public_page_text(url: str) -> str:
    """供 LangChain 工具调用：GET 单页并清洗为纯文本，失败时返回可读错误说明。"""
    u = (url or "").strip()
    if not u:
        return "[错误] URL 为空。"
    try:
        parsed = urlparse(u)
    except ValueError:
        return "[错误] URL 无法解析。"
    if parsed.scheme not in {"http", "https"} or not parsed.netloc:
        return "[错误] 仅支持 http/https 链接。"

    with httpx.Client(headers=_HTTP_HEADERS, timeout=_HTTP_TIMEOUT) as client:
        chunk, err = _fetch_url(client, u)
    if err:
        return f"[错误] {err}"
    return chunk if chunk else "(页面无正文)"


def search_public_web(query: str) -> str:
    """供 LangChain 工具调用：公开文本检索摘要。"""
    q = (query or "").strip()
    if not q:
        return "[错误] 查询关键词为空。"
    chunk, err = _search_duckduckgo(q)
    if err:
        return f"[说明] {err}"
    return chunk if chunk else "(无检索结果)"


def _search_query_from_brief(brief: str) -> str:
    text = (brief or "").strip()
    if not text:
        return ""
    first = text.splitlines()[0].strip()
    if len(first) >= 2:
        return first[:200]
    return text[:200]


def gather_brand_research(user_brief: str) -> tuple[str, list[str]]:
    """抓取 brief 中的链接并做公开检索，返回可拼进 LLM 的摘录与旁注。"""
    notes: list[str] = []
    if not _env_flag("BRAND_WEB_RESEARCH", _WEB_DEFAULT):
        return "", notes

    parts: list[str] = []
    urls = extract_urls(user_brief)

    with httpx.Client(headers=_HTTP_HEADERS, timeout=_HTTP_TIMEOUT) as client:
        for url in urls:
            chunk, err = _fetch_url(client, url)
            if err:
                notes.append(err)
            elif chunk:
                parts.append(chunk)

    query = _search_query_from_brief(user_brief)
    if query:
        s_chunk, s_err = _search_duckduckgo(query)
        if s_err:
            notes.append(s_err)
        elif s_chunk:
            parts.append(s_chunk)

    raw = "\n\n".join(parts).strip()
    if len(raw) > _MAX_CONTEXT_CHARS:
        raw = raw[:_MAX_CONTEXT_CHARS] + "\n…（摘录总长度已截断）"
        notes.append("摘录总长度已截断至配置上限。")

    return raw, notes
