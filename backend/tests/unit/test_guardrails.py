"""Tests for Guardrails."""
from __future__ import annotations

from guardrails.provider import AdLawGuardrail, BrandTabooGuardrail, ContentSafetyGuardrail
from guardrails.registry import GuardrailRegistry


class TestGuardrails:
    def test_ad_law_passes_clean_text(self) -> None:
        g = AdLawGuardrail()
        assert g.check("normal ad content").passed is True

    def test_ad_law_detects_violations(self) -> None:
        g = AdLawGuardrail()
        result = g.check("this has zui term")
        assert result.passed is False

    def test_brand_taboo(self) -> None:
        g = BrandTabooGuardrail()
        assert g.check("normal ad").passed is True
        assert g.check("jing pin").passed is False

    def test_content_safety(self) -> None:
        g = ContentSafetyGuardrail()
        assert g.check("normal content").passed is True
        assert g.check("se qing").passed is False

    def test_registry(self) -> None:
        registry = GuardrailRegistry()
        registry.register(AdLawGuardrail())
        assert len(registry.list_rules()) == 1
        results = registry.check_all("zui product")
        assert any(not r.passed for r in results)

    def test_is_all_passed(self) -> None:
        registry = GuardrailRegistry()
        registry.register(AdLawGuardrail())
        assert registry.is_all_passed("normal ad") is True
        assert registry.is_all_passed("zui product") is False

    def test_register_defaults(self) -> None:
        registry = GuardrailRegistry()
        registry.register(AdLawGuardrail())
        registry.register(BrandTabooGuardrail())
        registry.register(ContentSafetyGuardrail())
        assert len(registry.list_rules()) == 3