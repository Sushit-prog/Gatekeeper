from gatekeeper.models.requests import RuleResult
from gatekeeper.rules.base import SessionStateRecord, StatefulRule


class ScopeCreepRule(StatefulRule):
    """Blocks if a tool call references an entity previously marked as protected.

    This catches the core failure mode: an agent calls check_permissions(record_id=X)
    and learns X is restricted, then later calls delete_record(record_id=X) claiming
    "the restriction was for a different operation." ScopeCreepRule blocks this
    regardless of reasoning because it never sees the reasoning — only that record_id=X
    appears in session_history tagged as protected.
    """

    rule_id = "scope_creep"
    applies_to = ["*"]

    def __init__(self, rule_id: str = "scope_creep", tool_name: str = "*", tool_config: dict | None = None) -> None:
        self.rule_id = rule_id
        self.applies_to = [tool_name]
        creep_config = (tool_config or {}).get("scope_creep", {})
        self._protected_field: str = creep_config.get("protected_field", "record_id")
        self._protected_tag: str = creep_config.get("protected_tag", "protected_record_ids")

    async def evaluate(
        self,
        tool_name: str,
        args: dict,
        session_id: str,
        session_history: list[SessionStateRecord],
    ) -> RuleResult:
        # Collect all protected entity values from session history
        protected_values: set[str] = set()
        for record in session_history:
            if record.tags and self._protected_tag in record.tags:
                tag_values = record.tags[self._protected_tag]
                if isinstance(tag_values, list):
                    protected_values.update(str(v) for v in tag_values)
                elif isinstance(tag_values, str):
                    protected_values.add(tag_values)

        if not protected_values:
            return RuleResult(
                rule_id=self.rule_id,
                passed=True,
                reason="No protected entities in session history",
                severity="block",
                rule_type="stateful",
            )

        # Check if the current call references a protected entity
        current_value = args.get(self._protected_field)
        if current_value is None:
            return RuleResult(
                rule_id=self.rule_id,
                passed=True,
                reason=f"Field '{self._protected_field}' not present in args",
                severity="block",
                rule_type="stateful",
            )

        current_str = str(current_value)
        if current_str in protected_values:
            return RuleResult(
                rule_id=self.rule_id,
                passed=False,
                reason=(
                    f"Entity '{self._protected_field}={current_str}' was marked "
                    f"protected in a prior call in this session"
                ),
                severity="block",
                rule_type="stateful",
            )

        return RuleResult(
            rule_id=self.rule_id,
            passed=True,
            reason=f"Entity '{self._protected_field}={current_str}' is not protected",
            severity="block",
            rule_type="stateful",
        )
