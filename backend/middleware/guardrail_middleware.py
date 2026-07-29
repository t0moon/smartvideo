 from __future__ import annotations
 
 from typing import Any
 
 from guardrails.registry import GuardrailRegistry, get_registry
 from guardrails.provider import AdLawGuardrail, BrandTabooGuardrail, ContentSafetyGuardrail
 from events.bus import Event, get_event_bus, EVENT_GUARDRAIL_VIOLATION
 
 
 class GuardrailMiddleware:
     def __init__(self, registry: GuardrailRegistry | None = None) -> None:
         self.registry = registry or get_registry()
         if not self.registry.list_rules():
             self.registry.register(AdLawGuardrail())
             self.registry.register(BrandTabooGuardrail())
             self.registry.register(ContentSafetyGuardrail())
 
     def check_stage_output(self, stage: str, text: str, context: dict[str, Any] | None = None) -> list[dict]:
         results = self.registry.check_all(text, context)
         violations = []
         for result in results:
             if not result.passed:
                 violations.append({
                     'rule': result.rule,
                     'message': result.message,
                     'details': result.details,
                 })
         if violations:
             bus = get_event_bus()
             bus.publish(Event(
                 event_type=EVENT_GUARDRAIL_VIOLATION,
                 data={'stage': stage, 'violations': violations},
             ))
         return violations
