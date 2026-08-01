"""Format each review stage's content into Feishu-readable markdown.

Called by ``notify_review`` / ``send_review_card`` so that every HITL node
delivers the actual model output to the user *before* they see the
approve/reject buttons — giving them context to make an informed decision.
"""
from __future__ import annotations

from typing import Any


STAGE_NAMES: dict[str, str] = {
    "requirement": "\u9700\u6c42\u5206\u6790",
    "storyboard": "\u5206\u955c\u811a\u672c",
    "asset_prep": "\u7d20\u6750\u51c6\u5907",
    "video_review": "\u89c6\u9891\u5ba1\u6838",
}


def format_review_content(stage: str, content: dict[str, Any]) -> str:
    """Return a markdown string summarising the review payload for *stage*.

    Returns an empty string when the content has no displayable fields.
    """
    handler = _FORMATTERS.get(stage)
    return handler(content) if handler else ""


# ---------------------------------------------------------------------------
# Per-stage formatters
# ---------------------------------------------------------------------------

def _format_requirement(content: dict[str, Any]) -> str:
    spec = content.get("spec", content)  # tolerate flat or nested shapes
    lines: list[str] = []

    def _add(label: str, key: str, formatter=None) -> None:
        val = spec.get(key)
        if not val:
            return
        if formatter:
            val = formatter(val)
        lines.append(f"**{label}**\uff1a{val}")

    _add("\u89c6\u9891\u65f6\u957f", "duration_sec", lambda v: f"{v}\u79d2")
    _add("\u98ce\u683c", "style")
    _add("\u54c1\u724c", "brand")
    _add("\u4ea7\u54c1\u540d\u79f0", "product_name")
    _add("\u5e7f\u544a\u8bc9\u6c42", "ad_appeal")
    _add("\u76ee\u6807\u53d7\u4f17", "target_audience")
    _add("\u5e73\u53f0", "platform")
    _add("\u771f\u4eba\u51fa\u955c", "has_real_person", lambda v: "\u662f" if v else "\u5426")
    _add("\u8bed\u6c14\u8bed\u8c03", "tone_of_voice")

    kps = spec.get("key_selling_points")
    if kps:
        lines.append(f"**\u6838\u5fc3\u5356\u70b9**\uff1a{', '.join(kps)}")

    comp = spec.get("competitors")
    if comp:
        lines.append(f"**\u7ade\u4e89\u53c2\u8003**\uff1a{', '.join(comp)}")

    if spec.get("raw_brief") and spec["raw_brief"] != spec.get("style"):
        lines.append(f"**\u539f\u59cb\u7b80\u4ecb**\uff1a{spec['raw_brief'][:200]}")

    return "\n".join(lines) if lines else "\u2192 \u6a21\u578b\u5df2\u5b8c\u6210\u9700\u6c42\u5206\u6790\uff0c\u8bf7\u786e\u8ba4\u540e\u7ee7\u7eed\u3002"


def _format_storyboard(content: dict[str, Any]) -> str:
    sb = content.get("storyboard", content)
    # Prefer the human-readable text we embed during generation
    readable = sb.get("readable_text", "")
    if readable:
        return readable

    # Fallback: summary of scenes
    scenes = sb.get("scenes", [])
    if not scenes:
        return "\u2192 \u6a21\u578b\u5df2\u751f\u6210\u5206\u955c\u816a\u672c\uff0c\u8bf7\u786e\u8ba4\u540e\u7ee7\u7eed\u3002"
    parts = [f"\u5206\u955c\u811a\u672c\uff08{len(scenes)}\u573a\uff09\uff1a"]
    for i, s in enumerate(scenes, 1):
        title = s.get("title", f"\u573a\u666f{i}")
        desc = s.get("description", "")[:100]
        parts.append(f"\u573a\u666f{i}\uff1a**{title}** \u2014 {desc}")
    return "\n".join(parts)


def _format_asset_prep(content: dict[str, Any]) -> str:
    assets = content.get("assets", content)
    lines: list[str] = []

    chars = assets.get("suggested_characters", [])
    if chars:
        lines.append(f"**\u5efa\u8bae\u89d2\u8272**\uff08{len(chars)}\u4e2a\uff09\uff1a")
        for c in chars[:5]:
            role = c.get("role", "?")
            desc = c.get("description", "")[:80]
            digital = "\U0001F916\u6570\u5b57\u4eba" if c.get("use_digital_human") else "\U0001F464\u771f\u4eba"
            lines.append(f"  {digital} {role} \u2014 {desc}")

    voice = assets.get("suggested_voice", "")
    if voice and voice != "TBD":
        lines.append(f"**\u5efa\u8bae\u914d\u97f3**\uff1a{voice}")

    brand = assets.get("suggested_brand", "")
    if brand and brand != "TBD":
        lines.append(f"**\u54c1\u724c**\uff1a{brand}")

    platform = assets.get("platform", "")
    if platform and platform != "TBD":
        lines.append(f"**\u5e73\u53f0**\uff1a{platform}")

    style = assets.get("style_notes", "")
    if style:
        lines.append(f"**\u98ce\u683c\u5907\u6ce8**\uff1a{style[:200]}")

    if not lines:
        return "\u2192 \u7d20\u6750\u5efa\u8bae\u5df2\u751f\u6210\uff0c\u8bf7\u786e\u8ba4\u540e\u7ee7\u7eed\u3002"
    return "\n".join(lines)


def _format_video_review(content: dict[str, Any]) -> str:
    video = content.get("video", content)
    if isinstance(video, dict):
        count = video.get("clip_count", 0)
        if count:
            return f"\u89c6\u9891\u5df2\u751f\u6210\uff08{count}\u4e2a\u7247\u6bb5\uff09\uff0c\u8bf7\u786e\u8ba4\u540e\u7ee7\u7eed\u3002"
    return "\u89c6\u9891\u5df2\u751f\u6210\uff0c\u8bf7\u786e\u8ba4\u540e\u7ee7\u7eed\u3002"


_FORMATTERS: dict[str, Any] = {
    "requirement": _format_requirement,
    "storyboard": _format_storyboard,
    "asset_prep": _format_asset_prep,
    "video_review": _format_video_review,
}
