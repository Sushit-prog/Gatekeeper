import re

from gatekeeper.models.requests import RuleResult
from gatekeeper.rules.base import Rule

_PATTERNS: list[tuple[str, re.Pattern[str]]] = [
    ("email", re.compile(r"[\w.+-]+@[\w.-]+\.\w{2,}")),
    ("phone", re.compile(r"\b\d{3}[-.]?\d{3}[-.]?\d{4}\b")),
    ("ssn", re.compile(r"\b\d{3}-\d{2}-\d{4}\b")),
    ("credit_card", re.compile(r"\b\d{4}[\s-]?\d{4}[\s-]?\d{4}[\s-]?\d{4}\b")),
]


def _find_pii_in_values(values: list[str]) -> list[tuple[str, str]]:
    """Scan string values for PII patterns. Returns list of (type, matched_text)."""
    found: list[tuple[str, str]] = []
    for value in values:
        for pii_type, pattern in _PATTERNS:
            match = pattern.search(value)
            if match:
                found.append((pii_type, match.group()))
    return found


def _collect_string_values(obj: dict | list | str, exclude_fields: set[str] | None = None, _current_key: str | None = None) -> list[str]:
    """Recursively collect all string values from nested dicts/lists.

    Args:
        exclude_fields: Top-level field names to skip entirely.
        _current_key: Used internally to track the current dict key for exclusion.
    """
    values: list[str] = []
    if isinstance(obj, dict):
        for k, v in obj.items():
            if exclude_fields and k in exclude_fields:
                continue
            values.extend(_collect_string_values(v, exclude_fields, k))
    elif isinstance(obj, list):
        for item in obj:
            values.extend(_collect_string_values(item, exclude_fields, _current_key))
    elif isinstance(obj, str):
        values.append(obj)
    return values


class PIIDetectionRule(Rule):
    """Blocks requests containing PII (email, phone, SSN, credit card) in args.

    Configure pii_exclude_fields in policy to skip specific top-level fields
    (e.g. exclude "recipient" for send_email where email addresses are expected).
    """

    rule_id = "pii_detection"
    applies_to = ["*"]

    def __init__(self, rule_id: str = "pii_detection", tool_name: str = "*", tool_config: dict | None = None) -> None:
        self.rule_id = rule_id
        self.applies_to = [tool_name]
        self._exclude_fields: set[str] = set((tool_config or {}).get("pii_exclude_fields", []))

    def evaluate(self, tool_name: str, args: dict) -> RuleResult:
        string_values = _collect_string_values(args, self._exclude_fields)
        pii_found = _find_pii_in_values(string_values)

        if pii_found:
            pii_types = list({p[0] for p in pii_found})
            return RuleResult(
                rule_id=self.rule_id,
                passed=False,
                reason=f"PII detected: {', '.join(pii_types)}",
                severity="block",
            )

        return RuleResult(
            rule_id=self.rule_id,
            passed=True,
            reason="No PII detected in arguments",
            severity="block",
        )
