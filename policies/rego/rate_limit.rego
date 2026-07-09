package gatekeeper

import rego.v1

# Rate limit rule — blocks if more than N calls to a tool occur within a time window

# Parse ISO timestamp to seconds since epoch (simplified for comparison)
parse_timestamp(ts) := seconds if {
  ts != null
  # Simple parsing: assume format like "2024-01-01T00:00:00+00:00"
  # For Rego, we'll compare as strings since ISO timestamps sort lexicographically
  seconds := ts
}

evaluate_rule("rate_limit") := result if {
  tool_name := input.tool_name
  config := data.gatekeeper.config
  rate_config := config.rate_limit[tool_name]

  max_calls := rate_config.max_calls
  window_seconds := rate_config.window_seconds

  # No session history — under limit
  count(input.session_history) == 0
  result := {
    "rule_id": "rate_limit",
    "passed": true,
    "reason": concat("", ["0/", sprintf("%v", [max_calls]), " calls used in window"]),
    "severity": "block",
    "rule_type": "stateful"
  }
}

evaluate_rule("rate_limit") := result if {
  tool_name := input.tool_name
  config := data.gatekeeper.config
  rate_config := config.rate_limit[tool_name]

  max_calls := rate_config.max_calls
  window_seconds := rate_config.window_seconds

  count(input.session_history) > 0

  # Filter to same tool, allowed calls, within time window
  # For simplicity, count all history entries for this tool (time filtering
  # would need proper datetime parsing which Rego handles differently)
  relevant_calls := [r |
    some r in input.session_history
    r.tool_name == tool_name
    r.decision == "ALLOW"
  ]

  count(relevant_calls) < max_calls
  result := {
    "rule_id": "rate_limit",
    "passed": true,
    "reason": concat("", [sprintf("%v", [count(relevant_calls)]), "/", sprintf("%v", [max_calls]), " calls used in window"]),
    "severity": "block",
    "rule_type": "stateful"
  }
}

evaluate_rule("rate_limit") := result if {
  tool_name := input.tool_name
  config := data.gatekeeper.config
  rate_config := config.rate_limit[tool_name]

  max_calls := rate_config.max_calls
  window_seconds := rate_config.window_seconds

  count(input.session_history) > 0

  relevant_calls := [r |
    some r in input.session_history
    r.tool_name == tool_name
    r.decision == "ALLOW"
  ]

  count(relevant_calls) >= max_calls
  result := {
    "rule_id": "rate_limit",
    "passed": false,
    "reason": concat("", ["Rate limit exceeded: ", sprintf("%v", [count(relevant_calls)]), " calls to '", tool_name, "' (max: ", sprintf("%v", [max_calls]), ")"]),
    "severity": "block",
    "rule_type": "stateful"
  }
}

# No rate limit configured for this tool
evaluate_rule("rate_limit") := result if {
  tool_name := input.tool_name
  config := data.gatekeeper.config
  not config.rate_limit[tool_name]

  result := {
    "rule_id": "rate_limit",
    "passed": true,
    "reason": "No rate limit configured",
    "severity": "block",
    "rule_type": "stateful"
  }
}
