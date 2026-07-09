package gatekeeper

import rego.v1

# Denylist rule — blocks if args contain values matching a configured denylist

evaluate_rule("denylist") := result if {
  tool_name := input.tool_name
  args := input.args
  config := data.gatekeeper.config
  denylist_config := config.denylist[tool_name]

  field := denylist_config.field
  blocked_values := denylist_config.values
  target_value := sprintf("%v", [args[field]])

  # Check if any blocked value is contained in the target
  matches := [v | some v in blocked_values; contains(target_value, v)]
  count(matches) == 0

  result := {
    "rule_id": "denylist",
    "passed": true,
    "reason": concat("", ["No denylist matches in field '", field, "'"]),
    "severity": "block",
    "rule_type": "stateless"
  }
}

evaluate_rule("denylist") := result if {
  tool_name := input.tool_name
  args := input.args
  config := data.gatekeeper.config
  denylist_config := config.denylist[tool_name]

  field := denylist_config.field
  blocked_values := denylist_config.values
  target_value := sprintf("%v", [args[field]])

  matches := [v | some v in blocked_values; contains(target_value, v)]
  count(matches) > 0

  matched_value := matches[0]
  result := {
    "rule_id": "denylist",
    "passed": false,
    "reason": concat("", ["Value contains blocked entry: '", matched_value, "' in field '", field, "'"]),
    "severity": "block",
    "rule_type": "stateless"
  }
}

# Field not present in args — pass
evaluate_rule("denylist") := result if {
  tool_name := input.tool_name
  args := input.args
  config := data.gatekeeper.config
  denylist_config := config.denylist[tool_name]

  field := denylist_config.field
  not args[field]

  result := {
    "rule_id": "denylist",
    "passed": true,
    "reason": concat("", ["Field '", field, "' not present in args"]),
    "severity": "block",
    "rule_type": "stateless"
  }
}

# No denylist configured for this tool — pass
evaluate_rule("denylist") := result if {
  tool_name := input.tool_name
  config := data.gatekeeper.config
  not config.denylist[tool_name]

  result := {
    "rule_id": "denylist",
    "passed": true,
    "reason": "No denylist configured",
    "severity": "block",
    "rule_type": "stateless"
  }
}
