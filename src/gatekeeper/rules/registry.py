from pathlib import Path

import yaml

from gatekeeper.rules.base import Rule, StatefulRule
from gatekeeper.rules.builtin.argument_bounds import ArgumentBoundsRule
from gatekeeper.rules.builtin.denylist import DenylistRule
from gatekeeper.rules.builtin.pii_detection import PIIDetectionRule
from gatekeeper.rules.builtin.rate_limit import RateLimitRule
from gatekeeper.rules.builtin.scope_creep import ScopeCreepRule

_RULE_CLASSES: dict[str, type[Rule]] = {
    "pii_detection": PIIDetectionRule,
    "argument_bounds": ArgumentBoundsRule,
    "denylist": DenylistRule,
}

_STATEFUL_RULE_CLASSES: dict[str, type[StatefulRule]] = {
    "rate_limit": RateLimitRule,
    "scope_creep": ScopeCreepRule,
}


class RuleRegistry:
    """Loads the policy registry YAML and provides rule lookups."""

    def __init__(self, policy_path: str) -> None:
        self._policy_path = Path(policy_path)
        self._config: dict = {}
        self._tool_rules: dict[str, list[Rule]] = {}
        self._tool_stateful_rules: dict[str, list[StatefulRule]] = {}
        self._tag_tools: dict[str, dict] = {}
        self._load()

    def _load(self) -> None:
        if not self._policy_path.exists():
            return

        with open(self._policy_path) as f:
            self._config = yaml.safe_load(f) or {}

        tools = self._config.get("tools", {})
        for tool_name, tool_config in tools.items():
            # Load stateless rules
            rule_ids = tool_config.get("rules", [])
            rules: list[Rule] = []
            for rule_id in rule_ids:
                rule_cls = _RULE_CLASSES.get(rule_id)
                if rule_cls is None:
                    continue
                rules.append(rule_cls(rule_id=rule_id, tool_name=tool_name, tool_config=tool_config))
            self._tool_rules[tool_name] = rules

            # Load stateful rules
            stateful_ids = tool_config.get("stateful_rules", [])
            stateful_rules: list[StatefulRule] = []
            for rule_id in stateful_ids:
                rule_cls = _STATEFUL_RULE_CLASSES.get(rule_id)
                if rule_cls is None:
                    continue
                stateful_rules.append(rule_cls(rule_id=rule_id, tool_name=tool_name, tool_config=tool_config))
            self._tool_stateful_rules[tool_name] = stateful_rules

            # Load tag tools config
            tag_tools = tool_config.get("tag_tools")
            if tag_tools:
                self._tag_tools[tool_name] = tag_tools

    def get_applicable_rules(self, tool_name: str) -> list[Rule]:
        """Return stateless rules configured for this tool, or empty list for unknown tools."""
        return self._tool_rules.get(tool_name, [])

    def get_applicable_stateful_rules(self, tool_name: str) -> list[StatefulRule]:
        """Return stateful rules configured for this tool, or empty list."""
        return self._tool_stateful_rules.get(tool_name, [])

    def get_tag_tools_config(self) -> dict[str, dict]:
        """Return tag tool configurations: tool_name -> {protected_field, protected_tag}."""
        return self._tag_tools

    def get_policy_config(self) -> dict:
        """Return the raw policy configuration."""
        return self._config
