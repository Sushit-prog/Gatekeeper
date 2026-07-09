import pytest

from gatekeeper.rules.builtin.pii_detection import PIIDetectionRule


@pytest.fixture
def rule():
    return PIIDetectionRule()


@pytest.fixture
def rule_with_exclusion():
    return PIIDetectionRule(
        rule_id="pii_detection",
        tool_name="send_email",
        tool_config={"pii_exclude_fields": ["recipient"]},
    )


class TestPIIDetection:
    def test_blocks_email_in_args(self, rule):
        result = rule.evaluate("send_email", {"recipient": "user@example.com"})
        assert result.passed is False
        assert result.severity == "block"
        assert "email" in result.reason

    def test_blocks_phone_number(self, rule):
        result = rule.evaluate("send_email", {"body": "Call me at 555-123-4567"})
        assert result.passed is False
        assert "phone" in result.reason

    def test_blocks_ssn(self, rule):
        result = rule.evaluate("send_email", {"body": "SSN: 123-45-6789"})
        assert result.passed is False
        assert "ssn" in result.reason

    def test_blocks_credit_card(self, rule):
        result = rule.evaluate("send_email", {"body": "Card: 4111 1111 1111 1111"})
        assert result.passed is False
        assert "credit_card" in result.reason

    def test_passes_clean_args(self, rule):
        result = rule.evaluate("send_email", {"body": "Hello, no PII here"})
        assert result.passed is True

    def test_near_miss_extension_number(self, rule):
        result = rule.evaluate("send_email", {"body": "Call me at extension 5551234"})
        assert result.passed is True

    def test_blocks_nested_pii(self, rule):
        result = rule.evaluate("send_email", {"metadata": {"from": "alice@corp.com"}})
        assert result.passed is False

    def test_blocks_pii_in_list_values(self, rule):
        result = rule.evaluate("send_email", {"recipients": ["a@b.com", "clean"]})
        assert result.passed is False

    def test_multiple_pii_types(self, rule):
        result = rule.evaluate("send_email", {"body": "Email: x@y.com, SSN: 123-45-6789"})
        assert result.passed is False
        assert "email" in result.reason
        assert "ssn" in result.reason

    def test_clean_complex_args(self, rule):
        result = rule.evaluate("http_post", {
            "url": "https://api.example.com/data",
            "timeout": 30,
            "headers": {"Content-Type": "application/json"},
        })
        assert result.passed is True

    def test_excluded_field_not_checked(self, rule_with_exclusion):
        result = rule_with_exclusion.evaluate("send_email", {"recipient": "user@gmail.com", "body": "Hello"})
        assert result.passed is True

    def test_non_excluded_field_still_checked(self, rule_with_exclusion):
        result = rule_with_exclusion.evaluate("send_email", {"recipient": "user@gmail.com", "body": "SSN: 123-45-6789"})
        assert result.passed is False
        assert "ssn" in result.reason
