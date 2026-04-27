from __future__ import annotations

from typing import Any


def latest_human_text(messages: list[Any] | None) -> str:
    if not messages:
        return ""
    for m in reversed(messages):
        role = getattr(m, "type", None)
        if role == "human":
            content = getattr(m, "content", "")
            return content if isinstance(content, str) else str(content)
        name = m.__class__.__name__
        if name == "HumanMessage":
            content = getattr(m, "content", "")
            return content if isinstance(content, str) else str(content)
    return ""
