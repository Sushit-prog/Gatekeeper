package gatekeeper

import rego.v1

# Test scope creep rule

test_scope_creep_no_protected_allows if {
  result := evaluate_rule("scope_creep") with input as {
    "tool_name": "delete_record",
    "args": {"record_id": "rec-1"},
    "session_history": [
      {"tool_name": "delete_record", "args": {"record_id": "rec-1"}, "decision": "ALLOW", "tags": null, "created_at": null}
    ]
  }
  result.passed
}

test_scope_creep_protected_blocks if {
  result := evaluate_rule("scope_creep") with input as {
    "tool_name": "delete_record",
    "args": {"record_id": "rec-1"},
    "session_history": [
      {"tool_name": "check_permissions", "args": {"record_id": "rec-1"}, "decision": "ALLOW", "tags": {"protected_record_ids": ["rec-1"]}, "created_at": null}
    ]
  }
  not result.passed
  contains(result.reason, "marked protected")
}

test_scope_creep_different_entity_allows if {
  result := evaluate_rule("scope_creep") with input as {
    "tool_name": "delete_record",
    "args": {"record_id": "rec-2"},
    "session_history": [
      {"tool_name": "check_permissions", "args": {"record_id": "rec-1"}, "decision": "ALLOW", "tags": {"protected_record_ids": ["rec-1"]}, "created_at": null}
    ]
  }
  result.passed
}

test_scope_creep_empty_history_allows if {
  result := evaluate_rule("scope_creep") with input as {
    "tool_name": "delete_record",
    "args": {"record_id": "rec-1"},
    "session_history": []
  }
  result.passed
}

test_scope_creep_missing_field_allows if {
  result := evaluate_rule("scope_creep") with input as {
    "tool_name": "delete_record",
    "args": {"other_field": "value"},
    "session_history": [
      {"tool_name": "check_permissions", "args": {"record_id": "rec-1"}, "decision": "ALLOW", "tags": {"protected_record_ids": ["rec-1"]}, "created_at": null}
    ]
  }
  result.passed
  contains(result.reason, "not present")
}

test_scope_creep_multiple_protected if {
  result := evaluate_rule("scope_creep") with input as {
    "tool_name": "delete_record",
    "args": {"record_id": "rec-2"},
    "session_history": [
      {"tool_name": "check_permissions", "args": {"record_id": "rec-1"}, "decision": "ALLOW", "tags": {"protected_record_ids": ["rec-1"]}, "created_at": null},
      {"tool_name": "check_permissions", "args": {"record_id": "rec-2"}, "decision": "ALLOW", "tags": {"protected_record_ids": ["rec-2"]}, "created_at": null}
    ]
  }
  not result.passed
}
