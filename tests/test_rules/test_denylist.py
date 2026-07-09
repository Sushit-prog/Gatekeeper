import pytest

from gatekeeper.rules.builtin.denylist import DenylistRule


@pytest.fixture
def rule():
    tool_config = {
        "denylist": {
            "field": "url",
            "values": ["internal.corp", "localhost"],
        }
    }
    return DenylistRule(rule_id="denylist", tool_name="test_tool", tool_config=tool_config)


class TestDenylist:
    def test_blocks_denied_value(self, rule):
        result = rule.evaluate("test_tool", {"url": "https://internal.corp/api"})
        assert result.passed is False
        assert "internal.corp" in result.reason

    def test_blocks_partial_match(self, rule):
        result = rule.evaluate("test_tool", {"url": "http://localhost:8080"})
        assert result.passed is False

    def test_passes_clean_value(self, rule):
        result = rule.evaluate("test_tool", {"url": "https://api.example.com"})
        assert result.passed is True

    def test_passes_missing_field(self, rule):
        result = rule.evaluate("test_tool", {"other_field": "value"})
        assert result.passed is True

    def test_handles_no_config(self):
        rule = DenylistRule(rule_id="denylist", tool_name="test_tool", tool_config={})
        result = rule.evaluate("test_tool", {"url": "anything"})
        assert result.passed is True

    def test_numeric_value_coercion(self, rule):
        result = rule.evaluate("test_tool", {"url": 12345})
        assert result.passed is True
