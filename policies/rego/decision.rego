package gatekeeper

import rego.v1

# Top-level decision rule — combines all rule outputs into final ALLOW/BLOCK decision
# Mirrors PydanticRuleEngine's combination logic:
# - BLOCK if ANY block-severity rule failed
# - ALLOW otherwise
# - Warn-severity failures log but don't block

# Collect all rule results
all_rule_results := results if {
  results := [r |
    some rule_id in ["pii_detection", "argument_bounds", "denylist", "rate_limit", "scope_creep"]
    r := evaluate_rule(rule_id)
  ]
}

# Check if any block-severity rule failed
has_block_failure := true if {
  some r in all_rule_results
  r.severity == "block"
  not r.passed
}

# Final decision
default decision := {"decision": "ALLOW", "matched_rules": [], "latency_ms": 0}

decision := result if {
  not has_block_failure
  result := {
    "decision": "ALLOW",
    "matched_rules": all_rule_results,
    "latency_ms": 0
  }
}

decision := result if {
  has_block_failure
  result := {
    "decision": "BLOCK",
    "matched_rules": all_rule_results,
    "latency_ms": 0
  }
}

# Compute protection tags for tag tools
tags := result if {
  tool_name := input.tool_name
  config := data.gatekeeper.config
  tag_config := config.tag_tools[tool_name]
  decision.decision == "ALLOW"

  protected_field := tag_config.protected_field
  protected_tag := tag_config.protected_tag
  value := input.args[protected_field]
  value != null

  result := {protected_tag: [sprintf("%v", [value])]}
}

default tags := null
