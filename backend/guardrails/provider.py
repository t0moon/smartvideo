from __future__ import annotations

from typing import Any

from events.bus import Event, EventBus, get_event_bus, EVENT_GUARDRAIL_VIOLATION


class GuardrailResult:
    def __init__(self, passed: bool, rule: str, message: str = "", details: list[str] | None = None) -> None:
        self.passed = passed
        self.rule = rule
        self.message = message
        self.details = details or []

    def __bool__(self) -> bool:
        return self.passed


class BaseGuardrail:
    name: str = "base"

    def check(self, text: str, context: dict[str, Any] | None = None) -> GuardrailResult:
        raise NotImplementedError

    def _violation(self, rule: str, message: str, details: list[str] | None = None) -> GuardrailResult:
        return GuardrailResult(passed=False, rule=rule, message=message, details=details)

    def _pass(self) -> GuardrailResult:
        return GuardrailResult(passed=True, rule=self.name, message="Passed")


class AdLawGuardrail(BaseGuardrail):
    name = "ad_law"

    # 广告法绝对化用语 / 虚假宣传违禁词（中文，与 LLM 产出语言一致）
    _ABSOLUTE_TERMS = ["最好", "最佳", "最优", "第一", "顶级", "国家级", "唯一", "极致",
                        "史上最", "行业第一", "销量第一", "领导品牌", "领导地位"]
    _FORBIDDEN_TERMS = ["虚假", "伪造", "欺骗", "夸大", "绝对", "100%", "百分百", "保证效果"]

    def check(self, text: str, context: dict[str, Any] | None = None) -> GuardrailResult:
        violations: list[str] = []
        for term in self._ABSOLUTE_TERMS:
            if term in text.lower():
                violations.append(f'Absolute term: "{term}"')
        for term in self._FORBIDDEN_TERMS:
            if term in text.lower():
                violations.append(f'Forbidden term: "{term}"')
        if violations:
            bus = get_event_bus()
            bus.publish(Event(
                event_type=EVENT_GUARDRAIL_VIOLATION,
                data={"rule": self.name, "violations": violations, "text_preview": text[:200]},
            ))
            return self._violation(self.name, "Ad law compliance check failed", violations)
        return self._pass()


class BrandTabooGuardrail(BaseGuardrail):
    name = "brand_taboo"

    # 品牌禁忌：贬低竞品 / 暗示劣质等
    _COMMON_TABOO = ["竞品", "劣质", "质量差", "假货", "山寨", "差评", "性价比低"]

    def check(self, text: str, context: dict[str, Any] | None = None) -> GuardrailResult:
        violations = [f'Brand taboo: "{t}"' for t in self._COMMON_TABOO if t in text.lower()]
        if violations:
            bus = get_event_bus()
            bus.publish(Event(
                event_type=EVENT_GUARDRAIL_VIOLATION,
                data={"rule": self.name, "violations": violations},
            ))
            return self._violation(self.name, "Brand taboo check failed", violations)
        return self._pass()


class ContentSafetyGuardrail(BaseGuardrail):
    name = "content_safety"

    # 内容安全红线：命中即硬阻断
    _BLOCKED_CATEGORIES = ["暴力", "血腥", "色情", "政治敏感", "赌博", "毒品", "恐怖", "敏感"]

    def check(self, text: str, context: dict[str, Any] | None = None) -> GuardrailResult:
        violations = [f'Content safety: "{c}"' for c in self._BLOCKED_CATEGORIES if c in text.lower()]
        if violations:
            bus = get_event_bus()
            bus.publish(Event(
                event_type=EVENT_GUARDRAIL_VIOLATION,
                data={"rule": self.name, "violations": violations},
            ))
            return self._violation(self.name, "Content safety check failed", violations)
        return self._pass()
