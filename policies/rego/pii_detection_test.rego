package gatekeeper

import rego.v1

# Test PII detection rule

test_pii_blocks_email if {
  result := evaluate_rule("pii_detection") with input as {
    "tool_name": "http_post",
    "args": {"body": "Email: user@example.com"},
    "session_history": []
  }
  not result.passed
  result.rule_id == "pii_detection"
}

test_pii_blocks_phone if {
  result := evaluate_rule("pii_detection") with input as {
    "tool_name": "send_email",
    "args": {"body": "Call me at 555-123-4567"},
    "session_history": []
  }
  not result.passed
}

test_pii_blocks_ssn if {
  result := evaluate_rule("pii_detection") with input as {
    "tool_name": "send_email",
    "args": {"body": "SSN: 123-45-6789"},
    "session_history": []
  }
  not result.passed
}

test_pii_blocks_credit_card if {
  result := evaluate_rule("pii_detection") with input as {
    "tool_name": "send_email",
    "args": {"body": "Card: 4111 1111 1111 1111"},
    "session_history": []
  }
  not result.passed
}

test_pii_passes_clean_args if {
  result := evaluate_rule("pii_detection") with input as {
    "tool_name": "send_email",
    "args": {"body": "Hello, no PII here"},
    "session_history": []
  }
  result.passed
}

test_pii_near_miss_extension if {
  result := evaluate_rule("pii_detection") with input as {
    "tool_name": "send_email",
    "args": {"body": "Call me at extension 5551234"},
    "session_history": []
  }
  result.passed
}

test_pii_exclude_fields if {
  result := evaluate_rule("pii_detection") with input as {
    "tool_name": "send_email",
    "args": {"recipient": "user@gmail.com", "body": "Hello"},
    "session_history": []
  }
  result.passed
}

test_pii_blocks_in_body if {
  result := evaluate_rule("pii_detection") with input as {
    "tool_name": "http_post",
    "args": {"url": "https://api.example.com", "body": "Contact alice@corp.com for details"},
    "session_history": []
  }
  not result.passed
}
