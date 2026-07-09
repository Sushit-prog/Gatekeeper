from datetime import UTC, datetime, timedelta

from gatekeeper.models.requests import RuleResult
from gatekeeper.rules.base import SessionStateRecord, StatefulRule


class RateLimitRule(StatefulRule):
    """Blocks if more than N calls to a tool occur within a time window for a session."""

    rule_id = "rate_limit"
    applies_to = ["*"]

    def __init__(self, rule_id: str = "rate_limit", tool_name: str = "*", tool_config: dict | None = None) -> None:
        self.rule_id = rule_id
        self.applies_to = [tool_name]
        rate_config = (tool_config or {}).get("rate_limit", {})
        self._max_calls: int = rate_config.get("max_calls", 3)
        self._window_seconds: int = rate_config.get("window_seconds", 300)

    async def evaluate(
        self,
        tool_name: str,
        args: dict,
        session_id: str,
        session_history: list[SessionStateRecord],
    ) -> RuleResult:
        cutoff = datetime.now(UTC) - timedelta(seconds=self._window_seconds)

        # Count ALLOWED calls to this tool within the time window
        allowed_calls = sum(
            1 for record in session_history
            if record.tool_name == tool_name
            and record.decision == "ALLOW"
            and record.created_at >= cutoff
        )

        if allowed_calls >= self._max_calls:
            return RuleResult(
                rule_id=self.rule_id,
                passed=False,
                reason=(
                    f"Rate limit exceeded: {allowed_calls} calls to '{tool_name}' "
                    f"in last {self._window_seconds}s (max: {self._max_calls})"
                ),
                severity="block",
                rule_type="stateful",
            )

        return RuleResult(
            rule_id=self.rule_id,
            passed=True,
            reason=f"{allowed_calls}/{self._max_calls} calls used in window",
            severity="block",
            rule_type="stateful",
        )
