import pytest

from gatekeeper.rules.builtin.argument_bounds import ArgumentBoundsRule


@pytest.fixture
def rule():
    tool_config = {
        "argument_bounds": {
            "timeout": {"type": "int", "min": 1, "max": 300},
            "record_id": {"type": "str", "pattern": "^[0-9a-f]{8}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{12}$"},
            "body": {"type": "str", "max_length": 100},
        }
    }
    return ArgumentBoundsRule(rule_id="argument_bounds", tool_name="test_tool", tool_config=tool_config)


class TestArgumentBounds:
    def test_passes_within_bounds(self, rule):
        result = rule.evaluate("test_tool", {"timeout": 30})
        assert result.passed is True

    def test_blocks_below_minimum(self, rule):
        result = rule.evaluate("test_tool", {"timeout": 0})
        assert result.passed is False
        assert "below minimum" in result.reason

    def test_blocks_above_maximum(self, rule):
        result = rule.evaluate("test_tool", {"timeout": 500})
        assert result.passed is False
        assert "above maximum" in result.reason

    def test_blocks_bad_uuid_pattern(self, rule):
        result = rule.evaluate("test_tool", {"record_id": "not-a-uuid"})
        assert result.passed is False
        assert "does not match pattern" in result.reason

    def test_passes_valid_uuid(self, rule):
        result = rule.evaluate("test_tool", {"record_id": "550e8400-e29b-41d4-a716-446655440000"})
        assert result.passed is True

    def test_blocks_string_too_long(self, rule):
        result = rule.evaluate("test_tool", {"body": "x" * 101})
        assert result.passed is False
        assert "exceeds maximum" in result.reason

    def test_passes_string_within_limit(self, rule):
        result = rule.evaluate("test_tool", {"body": "x" * 100})
        assert result.passed is True

    def test_ignores_absent_fields(self, rule):
        result = rule.evaluate("test_tool", {"timeout": 30})
        assert result.passed is True

    def test_blocks_wrong_type(self, rule):
        result = rule.evaluate("test_tool", {"timeout": "not_an_int"})
        assert result.passed is False
        assert "expected int" in result.reason

    def test_multiple_violations(self, rule):
        result = rule.evaluate("test_tool", {"timeout": 500, "record_id": "bad"})
        assert result.passed is False
        assert "timeout" in result.reason
        assert "record_id" in result.reason
