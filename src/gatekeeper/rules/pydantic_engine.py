import time
from typing import Any

from gatekeeper.models.requests import GateDecision
from gatekeeper.rules.base import SessionStateRecord
from gatekeeper.rules.engine import RuleEngine
from gatekeeper.rules.registry import RuleRegistry


class PydanticRuleEngine(RuleEngine):
    """Pydantic-based rule engine — wraps M1/M2's existing evaluate_gate logic.

    This is a pure refactor: behavior is byte-for-byte unchanged from the
    original free function. Kept as the default engine and reference
    implementation.
    """

    def __init__(self, registry: RuleRegistry) -> None:
        self._registry = registry

    async def evaluate(
        self,
        tool_name: str,
        args: dict,
        session_history: list[SessionStateRecord],
    ) -> GateDecision:
        start = time.perf_counter()

        # 1. Run stateless rules (sync)
        applicable_rules = self._registry.get_applicable_rules(tool_name)
        results = [rule.evaluate(tool_name, args) for rule in applicable_rules]

        # 2. Run stateful rules (async)
        stateful_rules = self._registry.get_applicable_stateful_rules(tool_name)
        for rule in stateful_rules:
            result = await rule.evaluate(tool_name, args, "", session_history)
            results.append(result)

        # 3. Determine decision: BLOCK if ANY block-severity rule failed
        decision = "BLOCK" if any(
            r.severity == "block" and not r.passed for r in results
        ) else "ALLOW"

        # 4. Compute protection tags for tag tools
        tags = _compute_tags(tool_name, args, decision, self._registry)

        latency_ms = (time.perf_counter() - start) * 1000

        return GateDecision(
            decision=decision,
            matched_rules=results,
            latency_ms=latency_ms,
            audit_id="",
            tags=tags,
        )


def _compute_tags(
    tool_name: str,
    args: dict,
    decision: str,
    registry: RuleRegistry,
) -> dict[str, Any] | None:
    """Compute protection tags for tag tools."""
    tag_tools = registry.get_tag_tools_config()
    tool_config = tag_tools.get(tool_name)

    if not tool_config or decision != "ALLOW":
        return None

    protected_field = tool_config.get("protected_field", "")
    protected_tag = tool_config.get("protected_tag", "protected_record_ids")

    value = args.get(protected_field)
    if value is None:
        return None

    return {protected_tag: [str(value)]}
