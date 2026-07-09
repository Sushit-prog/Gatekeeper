import time

from gatekeeper.models.requests import GateCheckRequest, GateDecision
from gatekeeper.rules.registry import RuleRegistry


def evaluate_gate(request: GateCheckRequest, registry: RuleRegistry) -> GateDecision:
    """Evaluate a gate check request against all applicable rules.

    CRITICAL DESIGN PRINCIPLE:
    request.agent_reasoning is NEVER passed to any rule function.
    Only tool_name and args are extracted and forwarded to the rule engine.
    This is the structural isolation boundary — rules cannot access the
    agent's stated justification even if they wanted to.
    """
    start = time.perf_counter()

    applicable_rules = registry.get_applicable_rules(request.tool_name)
    results = [rule.evaluate(request.tool_name, request.args) for rule in applicable_rules]

    decision = "BLOCK" if any(
        r.severity == "block" and not r.passed for r in results
    ) else "ALLOW"

    latency_ms = (time.perf_counter() - start) * 1000

    return GateDecision(
        decision=decision,
        matched_rules=results,
        latency_ms=latency_ms,
        audit_id="",  # filled by audit logger after DB write
    )
