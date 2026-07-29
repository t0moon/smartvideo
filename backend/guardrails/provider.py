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

    _ABSOLUTE_TERMS = ["zui", "di yi", "ding ji", "guo jia ji"]
    _FORBIDDEN_TERMS = ["xu jia", "wei zao", "qi pian"]

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

    _COMMON_TABOO = ["jing pin", "lie zhi", "zhi liang cha"]

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

    _BLOCKED_CATEGORIES = ["bao li", "se qing", "zheng zhi min gan", "du bo", "du pin", "kong bu"]

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
