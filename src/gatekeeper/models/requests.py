from datetime import UTC, datetime
from typing import Any, Literal

from pydantic import BaseModel, Field


class GateCheckRequest(BaseModel):
    session_id: str
    tool_name: str
    args: dict[str, Any]
    agent_reasoning: str | None = None
    timestamp: datetime = Field(default_factory=lambda: datetime.now(UTC))


class RuleResult(BaseModel):
    rule_id: str
    passed: bool
    reason: str
    severity: Literal["block", "warn"]
    rule_type: Literal["stateless", "stateful"] = "stateless"


class GateDecision(BaseModel):
    decision: Literal["ALLOW", "BLOCK"]
    matched_rules: list[RuleResult]
    latency_ms: float
    audit_id: str
