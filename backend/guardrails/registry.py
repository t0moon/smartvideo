from __future__ import annotations

from typing import Any

from guardrails.provider import BaseGuardrail, GuardrailResult


class GuardrailRegistry:
    def __init__(self) -> None:
        self._guardrails: dict[str, BaseGuardrail] = {}

    def register(self, guardrail: BaseGuardrail) -> None:
        self._guardrails[guardrail.name] = guardrail

    def get(self, name: str) -> BaseGuardrail | None:
        return self._guardrails.get(name)

    def check_all(self, text: str, context: dict[str, Any] | None = None) -> list[GuardrailResult]:
        return [g.check(text, context) for g in self._guardrails.values()]

    def check(self, name: str, text: str, context: dict[str, Any] | None = None) -> GuardrailResult:
        guardrail = self.get(name)
        if not guardrail:
            return GuardrailResult(passed=True, rule=name, message='Guardrail not found')
        return guardrail.check(text, context)

    def is_all_passed(self, text: str, context: dict[str, Any] | None = None) -> bool:
        return all(g.check(text, context).passed for g in self._guardrails.values())

    def list_rules(self) -> list[str]:
        return list(self._guardrails.keys())


_registry = GuardrailRegistry()


def get_registry() -> GuardrailRegistry:
    return _registry


def register_defaults() -> None:
    from guardrails.provider import AdLawGuardrail, BrandTabooGuardrail, ContentSafetyGuardrail
    _registry.register(AdLawGuardrail())
    _registry.register(BrandTabooGuardrail())
    _registry.register(ContentSafetyGuardrail())
