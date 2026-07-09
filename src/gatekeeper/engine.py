import time
from typing import Any

from sqlalchemy.ext.asyncio import AsyncSession

from gatekeeper.audit.db import fetch_session_history_all_tools
from gatekeeper.models.requests import GateCheckRequest, GateDecision
from gatekeeper.rules.base import StatefulRule
from gatekeeper.rules.registry import RuleRegistry


async def evaluate_gate(
    request: GateCheckRequest,
    registry: RuleRegistry,
    session: AsyncSession | None = None,
) -> GateDecision:
    """Evaluate a gate check request against all applicable rules (stateless + stateful).

    CRITICAL DESIGN PRINCIPLE:
    request.agent_reasoning is NEVER passed to any rule function.
    Only tool_name and args are extracted and forwarded to the rule engine.
    This is the structural isolation boundary — rules cannot access the
    agent's stated justification even if they wanted to.

    If session is None, only stateless rules are evaluated (backward compat for tests).
    """
    start = time.perf_counter()

    # 1. Run stateless rules (sync, same as M1)
    applicable_rules = registry.get_applicable_rules(request.tool_name)
    results = [rule.evaluate(request.tool_name, request.args) for rule in applicable_rules]

    # 2. Fetch session history ONCE for stateful rules (only if session provided)
    #    Uses cross-tool history so scope_creep can see protection tags from other tools
    stateful_rules = registry.get_applicable_stateful_rules(request.tool_name)
    session_history: list = []
    if stateful_rules and session is not None:
        session_history = await fetch_session_history_all_tools(
            session, request.session_id
        )

    # 3. Run stateful rules (async)
    for rule in stateful_rules:
        result = await rule.evaluate(
            request.tool_name, request.args, request.session_id, session_history
        )
        results.append(result)

    # 4. Determine decision: BLOCK if ANY block-severity rule failed
    decision = "BLOCK" if any(
        r.severity == "block" and not r.passed for r in results
    ) else "ALLOW"

    # 5. Check if this is a tag tool that should write protection tags
    tags = _compute_tags(request, registry, decision)

    latency_ms = (time.perf_counter() - start) * 1000

    return GateDecision(
        decision=decision,
        matched_rules=results,
        latency_ms=latency_ms,
        audit_id="",  # filled by caller after DB write
        tags=tags,
    )


def _compute_tags(
    request: GateCheckRequest,
    registry: RuleRegistry,
    decision: str,
) -> dict[str, Any] | None:
    """Compute protection tags for tag tools.

    If the tool is configured as a tag tool and the decision is ALLOW,
    extract the protected entity value from args and return tags dict.
    """
    tag_tools = registry.get_tag_tools_config()
    tool_config = tag_tools.get(request.tool_name)

    if not tool_config or decision != "ALLOW":
        return None

    protected_field = tool_config.get("protected_field", "")
    protected_tag = tool_config.get("protected_tag", "protected_record_ids")

    value = request.args.get(protected_field)
    if value is None:
        return None

    return {protected_tag: [str(value)]}
