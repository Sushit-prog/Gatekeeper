package gatekeeper

import rego.v1

# Test denylist rule

test_denylist_blocks_denied_value if {
  result := evaluate_rule("denylist") with input as {
    "tool_name": "send_email",
    "args": {"recipient": "user@blocked-domain.com"},
    "session_history": []
  }
  not result.passed
  contains(result.reason, "blocked-domain.com")
}

test_denylist_blocks_partial_match if {
  result := evaluate_rule("denylist") with input as {
    "tool_name": "send_email",
    "args": {"recipient": "admin@blocked-domain.com"},
    "session_history": []
  }
  not result.passed
}

test_denylist_passes_clean_value if {
  result := evaluate_rule("denylist") with input as {
    "tool_name": "send_email",
    "args": {"recipient": "user@gmail.com"},
    "session_history": []
  }
  result.passed
}

test_denylist_passes_missing_field if {
  result := evaluate_rule("denylist") with input as {
    "tool_name": "send_email",
    "args": {"other_field": "value"},
    "session_history": []
  }
  result.passed
  contains(result.reason, "not present")
}

test_denylist_no_config_passes if {
  result := evaluate_rule("denylist") with input as {
    "tool_name": "unknown_tool",
    "args": {"url": "anything"},
    "session_history": []
  }
  result.passed
  contains(result.reason, "No denylist configured")
}
