import re

from gatekeeper.models.requests import RuleResult
from gatekeeper.rules.base import Rule


class ArgumentBoundsRule(Rule):
    """Validates numeric/string args against declared bounds from the policy config."""

    rule_id = "argument_bounds"
    applies_to = ["*"]

    def __init__(self, rule_id: str = "argument_bounds", tool_name: str = "*", tool_config: dict | None = None) -> None:
        self.rule_id = rule_id
        self.applies_to = [tool_name]
        self._bounds: dict[str, dict] = (tool_config or {}).get("argument_bounds", {})

    def evaluate(self, tool_name: str, args: dict) -> RuleResult:
        violations: list[str] = []

        for field, constraints in self._bounds.items():
            value = args.get(field)

            # If field is not present in args, skip (don't enforce absent fields)
            if value is None:
                continue

            # Type check
            expected_type = constraints.get("type")
            if expected_type == "int" and not isinstance(value, int):
                violations.append(f"{field}: expected int, got {type(value).__name__}")
                continue
            if expected_type == "str" and not isinstance(value, str):
                violations.append(f"{field}: expected str, got {type(value).__name__}")
                continue

            # Pattern check (strings only)
            pattern = constraints.get("pattern")
            if pattern and isinstance(value, str):
                if not re.match(pattern, value):
                    violations.append(f"{field}: does not match pattern {pattern}")

            # Numeric bounds
            if isinstance(value, (int, float)):
                if "min" in constraints and value < constraints["min"]:
                    violations.append(f"{field}: value {value} is below minimum {constraints['min']}")
                if "max" in constraints and value > constraints["max"]:
                    violations.append(f"{field}: value {value} is above maximum {constraints['max']}")

            # String length
            if isinstance(value, str):
                max_length = constraints.get("max_length")
                if max_length and len(value) > max_length:
                    violations.append(f"{field}: length {len(value)} exceeds maximum {max_length}")

        if violations:
            return RuleResult(
                rule_id=self.rule_id,
                passed=False,
                reason="; ".join(violations),
                severity="block",
            )

        return RuleResult(
            rule_id=self.rule_id,
            passed=True,
            reason="All arguments within declared bounds",
            severity="block",
        )
