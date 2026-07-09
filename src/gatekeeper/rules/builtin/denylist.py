from gatekeeper.models.requests import RuleResult
from gatekeeper.rules.base import Rule


class DenylistRule(Rule):
    """Blocks requests containing values matching a configured denylist."""

    rule_id = "denylist"
    applies_to = ["*"]

    def __init__(self, rule_id: str = "denylist", tool_name: str = "*", tool_config: dict | None = None) -> None:
        self.rule_id = rule_id
        self.applies_to = [tool_name]
        denylist_config = (tool_config or {}).get("denylist", {})
        self._field: str = denylist_config.get("field", "")
        self._values: list[str] = denylist_config.get("values", [])

    def evaluate(self, tool_name: str, args: dict) -> RuleResult:
        if not self._field or not self._values:
            return RuleResult(
                rule_id=self.rule_id,
                passed=True,
                reason="No denylist configured",
                severity="block",
            )

        target_value = args.get(self._field)
        if target_value is None:
            return RuleResult(
                rule_id=self.rule_id,
                passed=True,
                reason=f"Field '{self._field}' not present in args",
                severity="block",
            )

        target_str = str(target_value)
        for blocked in self._values:
            if blocked in target_str:
                return RuleResult(
                    rule_id=self.rule_id,
                    passed=False,
                    reason=f"Value contains blocked entry: '{blocked}' in field '{self._field}'",
                    severity="block",
                )

        return RuleResult(
            rule_id=self.rule_id,
            passed=True,
            reason=f"No denylist matches in field '{self._field}'",
            severity="block",
        )
