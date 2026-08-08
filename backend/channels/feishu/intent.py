"""Intent parser: extract approval/rejection/feedback from user text.

Pure keyword-rules parser — no LLM needed for this. The parser supports
two key patterns that a card-less, conversation-driven HITL loop requires:

1. Pure approve:  "批准" / "通过" / "ok"
2. Reject only:   "驳回" / "拒绝" / "不对"
3. **Reject with feedback**: "驳回 改成暖色调" / "拒绝 第三个场景不对"
   → parser extracts the feedback portion so the pipeline can do a
   partial_revision with the user's edit notes.

A separate "clarify" intent handles "什么意思" / "再说一遍" — the bot
re-sends the review content.
"""
from __future__ import annotations


# Keep these synced with _handle_im_message's keywords (they diverge now:
# ws_listener's keyword check acts as an early-exit for 'new_project' routing;
# the full parse happens here once ConversationRouter.route() is entered).
APPROVE_KEYWORDS = {
    "批准", "同意", "通过", "approve", "ok", "好的", "yes", "y",
    "没问题", "可以", "行", "好", "继续", "下一步",
}
REJECT_HEAD_KEYWORDS = {
    "驳回", "拒绝", "不通过", "reject", "no", "否", "重新做", "不对",
    "不行", "不好", "重新来", "重做", "改一下", "改改",
}
CLARIFY_KEYWORDS = {
    "什么意思", "再说一遍", "没看懂", "解释", "重发", "再说一下",
}


def parse_intent(text: str) -> tuple[str, str]:
    """Return (intent, feedback_text).

    intents:
      - "approve"          user approves as-is
      - "reject"           user rejects with no specific feedback
      - "reject_feedback"  user rejects with modification notes
      - "clarify"          user wants the bot to re-explain
      - "unrelated"        none of the above
    """
    t = text.strip()
    lower = t.lower()

    # ── exact approve match ───────────────────────────────────────────
    if lower in APPROVE_KEYWORDS:
        return ("approve", "")

    # ── clarify ───────────────────────────────────────────────────────
    if lower in CLARIFY_KEYWORDS or any(k in lower for k in CLARIFY_KEYWORDS if len(k) > 2):
        return ("clarify", "")

    # ── reject (possibly with feedback) ───────────────────────────────
    # Detect a reject intent at the START (or standalone) and separate
    # any following feedback text.
    reject_word = _starts_with_any(lower, REJECT_HEAD_KEYWORDS)
    if reject_word:
        # Extract everything after the reject keyword as feedback
        tail = t[len(reject_word):].strip()
        # Strip leading punctuation / separators
        while tail and tail[0] in ",，.。:：;；!！-— ":
            tail = tail[1:].strip()
        if tail:
            return ("reject_feedback", tail)
        return ("reject", "")

    # ── heuristic: feedback-like without explicit '驳回' (user replies
    #     directly with change requests e.g. "改成15秒" "暖色调更好") ──
    if any(ptr in lower for ptr in ("改成", "改为", "换成", "去掉", "加", "增加", "减少",
                                     "太冷", "太暖", "太长", "太短", "错了", "不对", "不对应")):
        return ("reject_feedback", t)

    return ("unrelated", "")


def _starts_with_any(text: str, keywords: set[str]) -> str | None:
    """Return the matching keyword if *text* starts with any of *keywords*.
    Handles the case where the keyword is followed by whitespace/punctuation.
    """
    lower = text.lower()
    for kw in sorted(keywords, key=len, reverse=True):  # longest match first
        if lower.startswith(kw):
            return kw
        if lower.startswith(kw + " ") or lower.startswith(kw + ",") or lower.startswith(kw + "，"):
            return kw
    return None
