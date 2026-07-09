from pathlib import Path

import yaml

from gatekeeper.rules.base import Rule
from gatekeeper.rules.builtin.argument_bounds import ArgumentBoundsRule
from gatekeeper.rules.builtin.denylist import DenylistRule
from gatekeeper.rules.builtin.pii_detection import PIIDetectionRule

_RULE_CLASSES: dict[str, type[Rule]] = {
    "pii_detection": PIIDetectionRule,
    "argument_bounds": ArgumentBoundsRule,
    "denylist": DenylistRule,
}


class RuleRegistry:
    """Loads the policy registry YAML and provides rule lookups."""

    def __init__(self, policy_path: str) -> None:
        self._policy_path = Path(policy_path)
        self._config: dict = {}
        self._tool_rules: dict[str, list[Rule]] = {}
        self._load()

    def _load(self) -> None:
        if not self._policy_path.exists():
            return

        with open(self._policy_path) as f:
            self._config = yaml.safe_load(f) or {}

        tools = self._config.get("tools", {})
        for tool_name, tool_config in tools.items():
            rule_ids = tool_config.get("rules", [])
            rules: list[Rule] = []
            for rule_id in rule_ids:
                rule_cls = _RULE_CLASSES.get(rule_id)
                if rule_cls is None:
                    continue
                # Pass the full tool_config to rules that need it
                rules.append(rule_cls(rule_id=rule_id, tool_name=tool_name, tool_config=tool_config))
            self._tool_rules[tool_name] = rules

    def get_applicable_rules(self, tool_name: str) -> list[Rule]:
        """Return rules configured for this tool, or empty list for unknown tools."""
        return self._tool_rules.get(tool_name, [])

    def get_policy_config(self) -> dict:
        """Return the raw policy configuration."""
        return self._config
