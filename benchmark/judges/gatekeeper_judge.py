"""GateKeeper judge — calls the PydanticRuleEngine directly to evaluate a tool call.

Uses the engine directly instead of the HTTP API so that session_history
from the scenario is passed directly to the rules (bypassing the DB).
"""

from datetime import UTC, datetime

from gatekeeper.models.requests import GateCheckRequest
from gatekeeper.rules.base import SessionStateRecord
from gatekeeper.rules.pydantic_engine import PydanticRuleEngine
from gatekeeper.rules.registry import RuleRegistry


def _convert_history(session_history: list[dict]) -> list[SessionStateRecord]:
    """Convert benchmark SessionRecord dicts to engine SessionStateRecord objects."""
    records = []
    for r in session_history:
        records.append(
            SessionStateRecord(
                session_id="benchmark",
                tool_name=r.get("tool_name", ""),
                args=r.get("args", {}),
                decision=r.get("decision", "ALLOW"),
                tags=r.get("tags"),
                created_at=datetime.now(UTC),
            )
        )
    return records


# Module-level singleton — created once, reused across calls
_registry: RuleRegistry | None = None
_engine: PydanticRuleEngine | None = None


def _get_engine() -> PydanticRuleEngine:
    global _registry, _engine
    if _engine is None:
        _registry = RuleRegistry("policies/policy_registry.yaml")
        _engine = PydanticRuleEngine(_registry)
    return _engine


async def judge(
    tool_name: str,
    args: dict,
    agent_reasoning: str,
    session_history: list[dict],
    session_id: str = "benchmark",
    gate_url: str = "http://localhost:8000",
) -> dict:
    """Evaluate a tool call using GateKeeper's PydanticRuleEngine directly.

    Returns:
        {"decision": "allow"|"block", "reason": str}
    """
    try:
        engine = _get_engine()
        history = _convert_history(session_history)
        decision = await engine.evaluate(tool_name, args, history)

        # Find the first failed rule for the reason
        reason = "No rules matched"
        for rule in decision.matched_rules:
            if not rule.passed:
                reason = rule.reason
                break

        return {
            "decision": decision.decision.lower(),
            "reason": reason,
        }
    except Exception as e:
        return {"decision": "block", "reason": f"GateKeeper error: {e}"}
