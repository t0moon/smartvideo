"""Feishu card message builder utilities."""
from __future__ import annotations

from typing import Any


def build_review_card(review_id: str, project_id: str, stage: str, project_name: str = "", review_content: str = "") -> dict[str, Any]:
    elements: list[dict] = [
        {"tag": "markdown", "content": f"\u9879\u76ee **{project_name or project_id}** \u9700\u8981\u5728 **{stage}** \u9636\u6bb5\u8fdb\u884c\u5ba1\u6279"},
    ]
    if review_content:
        elements.append({"tag": "markdown", "content": f"\u5ba1\u6838\u5185\u5bb9\uff1a{review_content[:200]}"})
    elements.append({"tag": "hr"})
    elements.append({
        "tag": "action",
        "actions": [
            {"tag": "button", "text": {"tag": "plain_text", "content": "\u6279\u51c6"}, "type": "primary",
             "value": {"action": "approve", "review_id": review_id}},
            {"tag": "button", "text": {"tag": "plain_text", "content": "\u67e5\u770b\u8be6\u60c5"}, "type": "default",
             "value": {"action": "view", "project_id": project_id}},
            {"tag": "button", "text": {"tag": "plain_text", "content": "\u9a73\u56de"}, "type": "danger",
             "value": {"action": "reject", "review_id": review_id}},
        ],
    })
    return {
        "config": {"wide_screen_mode": True, "enable_forward": True},
        "header": {"title": {"tag": "plain_text", "content": f"\u5ba1\u6279\u901a\u77e5: {stage}"}, "template": "blue"},
        "elements": elements,
    }


def build_status_card(project_id: str, stage: str, status: str, message: str = "") -> dict[str, Any]:
    color = {"completed": "green", "failed": "red", "paused": "yellow", "running": "blue"}.get(status, "grey")
    elements: list[dict] = [{"tag": "markdown", "content": f"\u9879\u76ee **{project_id}** \u72b6\u6001\u66f4\u65b0"}, {"tag": "markdown", "content": f"\u5f53\u524d\u9636\u6bb5\uff1a{stage}"}]
    if message:
        elements.append({"tag": "markdown", "content": message})
    return {"config": {"wide_screen_mode": True}, "header": {"title": {"tag": "plain_text", "content": f"[{status.upper()}] {stage}"}, "template": color}, "elements": elements}