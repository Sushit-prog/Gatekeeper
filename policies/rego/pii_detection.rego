package gatekeeper

import rego.v1

# PII detection rule — blocks if args contain email, phone, SSN, or credit card patterns
# Respects pii_exclude_fields configuration from data

pii_patterns := {
  "email": "[\\w.+-]+@[\\w.-]+\\.\\w{2,}",
  "phone": "\\b\\d{3}[-.]?\\d{3}[-.]?\\d{4}\\b",
  "ssn": "\\b\\d{3}-\\d{2}-\\d{4}\\b",
  "credit_card": "\\b\\d{4}[\\s-]?\\d{4}[\\s-]?\\d{4}[\\s-]?\\d{4}\\b"
}

# Collect all string values from a flat object (non-recursive for Rego compatibility)
collect_string_values(obj, exclude_fields) := output if {
  output := [v |
    some key, val in obj
    not key in exclude_fields
    is_string(val)
    v := val
  ]
}

# Check if any string matches a PII pattern
find_pii(values) := output if {
  output := [m |
    some val in values
    some pii_type, pattern in pii_patterns
    regex.match(pattern, val)
    m := {"type": pii_type, "value": val}
  ]
}

# Main PII detection rule
evaluate_rule("pii_detection") := result if {
  tool_name := input.tool_name
  args := input.args
  config := data.gatekeeper.config

  # Get exclude fields for this tool
  exclude_fields := {f | f := config.pii_exclude_fields[tool_name][_]}

  # Collect string values excluding specified fields
  all_values := collect_string_values(args, exclude_fields)

  # Find PII matches
  pii_matches := find_pii(all_values)

  count(pii_matches) == 0
  result := {
    "rule_id": "pii_detection",
    "passed": true,
    "reason": "No PII detected in arguments",
    "severity": "block",
    "rule_type": "stateless"
  }
}

evaluate_rule("pii_detection") := result if {
  tool_name := input.tool_name
  args := input.args
  config := data.gatekeeper.config

  exclude_fields := {f | f := config.pii_exclude_fields[tool_name][_]}

  all_values := collect_string_values(args, exclude_fields)
  pii_matches := find_pii(all_values)

  count(pii_matches) > 0
  pii_types := {m.type | m := pii_matches[_]}
  type_list := concat(", ", [t | t := pii_types[_]])
  result := {
    "rule_id": "pii_detection",
    "passed": false,
    "reason": concat("", ["PII detected: ", type_list]),
    "severity": "block",
    "rule_type": "stateless"
  }
}
