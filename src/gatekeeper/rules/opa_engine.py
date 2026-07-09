import time
from datetime import UTC, datetime

import httpx
import structlog

from gatekeeper.models.requests import GateDecision, RuleResult
from gatekeeper.rules.base import SessionStateRecord
from gatekeeper.rules.engine import RuleEngine

logger = structlog.get_logger()


class OPARuleEngine(RuleEngine):
    """OPA-based rule engine — queries OPA server over HTTP.

    OPA receives { tool_name, args, session_history } as input and returns
    a decision. If OPA is unreachable, returns BLOCK (infrastructure failure).
    """

    def __init__(self, opa_url: str = "http://localhost:8181") -> None:
        self._opa_url = opa_url.rstrip("/")
        self._decision_url = f"{self._opa_url}/v1/data/gatekeeper/decision"
        self._client = httpx.AsyncClient(timeout=5.0)

    async def close(self) -> None:
        await self._client.aclose()

    async def evaluate(
        self,
        tool_name: str,
        args: dict,
        session_history: list[SessionStateRecord],
    ) -> GateDecision:
        start = time.perf_counter()

        # Build input document for OPA
        input_doc = {
            "input": {
                "tool_name": tool_name,
                "args": args,
                "session_history": [
                    {
                        "tool_name": r.tool_name,
                        "args": r.args,
                        "decision": r.decision,
                        "tags": r.tags,
                        "created_at": r.created_at.isoformat() if r.created_at else None,
                    }
                    for r in session_history
                ],
            }
        }

        try:
            response = await self._client.post(self._decision_url, json=input_doc)
            response.raise_for_status()
            result = response.json()
        except (httpx.ConnectError, httpx.HTTPStatusError, httpx.TimeoutException) as e:
            logger.error("opa_unreachable", error=str(e))
            latency_ms = (time.perf_counter() - start) * 1000
            return GateDecision(
                decision="BLOCK",
                matched_rules=[
                    RuleResult(
                        rule_id="opa_health",
                        passed=False,
                        reason=f"OPA server unreachable: {e}",
                        severity="block",
                        rule_type="stateful",
                    )
                ],
                latency_ms=latency_ms,
                audit_id="",
            )

        return _parse_opa_response(result, start)


def _parse_opa_response(result: dict, start_time: float) -> GateDecision:
    """Convert OPA's response into GateDecision."""
    result_data = result.get("result", {})

    decision = result_data.get("decision", "ALLOW")
    matched_rules_raw = result_data.get("matched_rules", [])

    matched_rules = [
        RuleResult(
            rule_id=r.get("rule_id", "unknown"),
            passed=r.get("passed", True),
            reason=r.get("reason", ""),
            severity=r.get("severity", "block"),
            rule_type=r.get("rule_type", "stateless"),
        )
        for r in matched_rules_raw
    ]

    latency_ms = (time.perf_counter() - start_time) * 1000

    return GateDecision(
        decision=decision,
        matched_rules=matched_rules,
        latency_ms=latency_ms,
        audit_id="",
    )
