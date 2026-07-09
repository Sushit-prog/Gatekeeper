package gatekeeper

import rego.v1

# Argument bounds rule — validates numeric/string args against declared bounds

check_type(value, expected_type) if {
  expected_type == "int"
  is_number(value)
  value == floor(value)
}

check_type(value, expected_type) if {
  expected_type == "str"
  is_string(value)
}

check_pattern(value, pattern) if {
  is_string(value)
  regex.match(pattern, value)
}

check_min(value, min_val) if {
  is_number(value)
  value >= min_val
}

check_max(value, max_val) if {
  is_number(value)
  value <= max_val
}

check_max_length(value, max_len) if {
  is_string(value)
  count(value) <= max_len
}

evaluate_rule("argument_bounds") := result if {
  tool_name := input.tool_name
  args := input.args
  config := data.gatekeeper.config
  bounds := config.argument_bounds[tool_name]

  violations := [v |
    some field, constraints in bounds
    value := args[field]
    v := check_field_violations(field, value, constraints)
    v != ""
  ]

  count(violations) == 0
  result := {
    "rule_id": "argument_bounds",
    "passed": true,
    "reason": "All arguments within declared bounds",
    "severity": "block",
    "rule_type": "stateless"
  }
}

evaluate_rule("argument_bounds") := result if {
  tool_name := input.tool_name
  args := input.args
  config := data.gatekeeper.config
  bounds := config.argument_bounds[tool_name]

  violations := [v |
    some field, constraints in bounds
    value := args[field]
    v := check_field_violations(field, value, constraints)
    v != ""
  ]

  count(violations) > 0
  reason := concat("; ", violations)
  result := {
    "rule_id": "argument_bounds",
    "passed": false,
    "reason": reason,
    "severity": "block",
    "rule_type": "stateless"
  }
}

# No bounds configured for this tool
evaluate_rule("argument_bounds") := result if {
  tool_name := input.tool_name
  config := data.gatekeeper.config
  not config.argument_bounds[tool_name]
  result := {
    "rule_id": "argument_bounds",
    "passed": true,
    "reason": "No bounds configured for this tool",
    "severity": "block",
    "rule_type": "stateless"
  }
}

check_field_violations(field, value, constraints) := msg if {
  expected_type := constraints.type
  not check_type(value, expected_type)
  msg := concat("", [field, ": expected ", expected_type])
}

check_field_violations(field, value, constraints) := msg if {
  pattern := constraints.pattern
  is_string(value)
  not regex.match(pattern, value)
  msg := concat("", [field, ": does not match pattern ", pattern])
}

check_field_violations(field, value, constraints) := msg if {
  min_val := constraints.min
  is_number(value)
  value < min_val
  msg := concat("", [field, ": value ", sprintf("%v", [value]), " is below minimum ", sprintf("%v", [min_val])])
}

check_field_violations(field, value, constraints) := msg if {
  max_val := constraints.max
  is_number(value)
  value > max_val
  msg := concat("", [field, ": value ", sprintf("%v", [value]), " is above maximum ", sprintf("%v", [max_val])])
}

check_field_violations(field, value, constraints) := msg if {
  max_len := constraints.max_length
  is_string(value)
  count(value) > max_len
  msg := concat("", [field, ": length ", sprintf("%v", [count(value)]), " exceeds maximum ", sprintf("%v", [max_len])])
}
