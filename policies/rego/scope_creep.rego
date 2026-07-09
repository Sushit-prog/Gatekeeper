package gatekeeper

import rego.v1

# Scope creep rule — blocks if args reference an entity previously marked as protected

evaluate_rule("scope_creep") := result if {
  tool_name := input.tool_name
  args := input.args
  config := data.gatekeeper.config
  creep_config := config.scope_creep[tool_name]

  protected_field := creep_config.protected_field
  protected_tag := creep_config.protected_tag

  # No session history — no protected entities
  count(input.session_history) == 0
  result := {
    "rule_id": "scope_creep",
    "passed": true,
    "reason": "No protected entities in session history",
    "severity": "block",
    "rule_type": "stateful"
  }
}

evaluate_rule("scope_creep") := result if {
  tool_name := input.tool_name
  args := input.args
  config := data.gatekeeper.config
  creep_config := config.scope_creep[tool_name]

  protected_field := creep_config.protected_field
  protected_tag := creep_config.protected_tag

  count(input.session_history) > 0

  # Collect all protected entity values from session history
  protected_values := {v |
    some record in input.session_history
    record.tags != null
    tags := record.tags
    tag_values := tags[protected_tag]
    v := tag_values[_]
  }

  count(protected_values) == 0
  result := {
    "rule_id": "scope_creep",
    "passed": true,
    "reason": "No protected entities in session history",
    "severity": "block",
    "rule_type": "stateful"
  }
}

evaluate_rule("scope_creep") := result if {
  tool_name := input.tool_name
  args := input.args
  config := data.gatekeeper.config
  creep_config := config.scope_creep[tool_name]

  protected_field := creep_config.protected_field
  protected_tag := creep_config.protected_tag

  count(input.session_history) > 0

  protected_values := {v |
    some record in input.session_history
    record.tags != null
    tags := record.tags
    tag_values := tags[protected_tag]
    v := tag_values[_]
  }

  count(protected_values) > 0

  # Check if current call references a protected entity
  current_value := sprintf("%v", [args[protected_field]])
  current_value in protected_values

  result := {
    "rule_id": "scope_creep",
    "passed": false,
    "reason": concat("", ["Entity '", protected_field, "=", current_value, "' was marked protected in a prior call in this session"]),
    "severity": "block",
    "rule_type": "stateful"
  }
}

evaluate_rule("scope_creep") := result if {
  tool_name := input.tool_name
  args := input.args
  config := data.gatekeeper.config
  creep_config := config.scope_creep[tool_name]

  protected_field := creep_config.protected_field
  protected_tag := creep_config.protected_tag

  count(input.session_history) > 0

  protected_values := {v |
    some record in input.session_history
    record.tags != null
    tags := record.tags
    tag_values := tags[protected_tag]
    v := tag_values[_]
  }

  count(protected_values) > 0

  current_value := sprintf("%v", [args[protected_field]])
  not current_value in protected_values

  result := {
    "rule_id": "scope_creep",
    "passed": true,
    "reason": concat("", ["Entity '", protected_field, "=", current_value, "' is not protected"]),
    "severity": "block",
    "rule_type": "stateful"
  }
}

# Field not present in args — pass
evaluate_rule("scope_creep") := result if {
  tool_name := input.tool_name
  args := input.args
  config := data.gatekeeper.config
  creep_config := config.scope_creep[tool_name]

  protected_field := creep_config.protected_field
  not args[protected_field]

  result := {
    "rule_id": "scope_creep",
    "passed": true,
    "reason": concat("", ["Field '", protected_field, "' not present in args"]),
    "severity": "block",
    "rule_type": "stateful"
  }
}

# No scope creep config for this tool
evaluate_rule("scope_creep") := result if {
  tool_name := input.tool_name
  config := data.gatekeeper.config
  not config.scope_creep[tool_name]

  result := {
    "rule_id": "scope_creep",
    "passed": true,
    "reason": "No scope creep rules configured",
    "severity": "block",
    "rule_type": "stateful"
  }
}
