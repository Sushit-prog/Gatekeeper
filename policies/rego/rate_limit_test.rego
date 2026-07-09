package gatekeeper

import rego.v1

# Test rate limit rule

test_rate_limit_under_limit if {
  result := evaluate_rule("rate_limit") with input as {
    "tool_name": "delete_record",
    "args": {"record_id": "rec-1"},
    "session_history": [
      {"tool_name": "delete_record", "args": {}, "decision": "ALLOW", "tags": null, "created_at": null},
      {"tool_name": "delete_record", "args": {}, "decision": "ALLOW", "tags": null, "created_at": null}
    ]
  }
  result.passed
  contains(result.reason, "2/3")
}

test_rate_limit_at_limit if {
  result := evaluate_rule("rate_limit") with input as {
    "tool_name": "delete_record",
    "args": {"record_id": "rec-1"},
    "session_history": [
      {"tool_name": "delete_record", "args": {}, "decision": "ALLOW", "tags": null, "created_at": null},
      {"tool_name": "delete_record", "args": {}, "decision": "ALLOW", "tags": null, "created_at": null},
      {"tool_name": "delete_record", "args": {}, "decision": "ALLOW", "tags": null, "created_at": null}
    ]
  }
  not result.passed
  contains(result.reason, "Rate limit exceeded")
}

test_rate_limit_empty_history if {
  result := evaluate_rule("rate_limit") with input as {
    "tool_name": "delete_record",
    "args": {"record_id": "rec-1"},
    "session_history": []
  }
  result.passed
}

test_rate_limit_only_allowed_count if {
  result := evaluate_rule("rate_limit") with input as {
    "tool_name": "delete_record",
    "args": {"record_id": "rec-1"},
    "session_history": [
      {"tool_name": "delete_record", "args": {}, "decision": "ALLOW", "tags": null, "created_at": null},
      {"tool_name": "delete_record", "args": {}, "decision": "BLOCK", "tags": null, "created_at": null}
    ]
  }
  result.passed
  contains(result.reason, "1/3")
}

test_rate_limit_different_tool_not_counted if {
  result := evaluate_rule("rate_limit") with input as {
    "tool_name": "delete_record",
    "args": {"record_id": "rec-1"},
    "session_history": [
      {"tool_name": "send_email", "args": {}, "decision": "ALLOW", "tags": null, "created_at": null},
      {"tool_name": "send_email", "args": {}, "decision": "ALLOW", "tags": null, "created_at": null}
    ]
  }
  result.passed
  contains(result.reason, "0/3")
}
