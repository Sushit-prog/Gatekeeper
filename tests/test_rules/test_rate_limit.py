from datetime import UTC, datetime, timedelta

import pytest

from gatekeeper.rules.base import SessionStateRecord
from gatekeeper.rules.builtin.rate_limit import RateLimitRule


@pytest.fixture
def rule():
    tool_config = {"rate_limit": {"max_calls": 3, "window_seconds": 300}}
    return RateLimitRule(rule_id="rate_limit", tool_name="delete_record", tool_config=tool_config)


def _make_history(count: int, tool_name: str = "delete_record", decision: str = "ALLOW",
                  window_start: datetime | None = None) -> list[SessionStateRecord]:
    """Create mock session history with `count` records."""
    if window_start is None:
        # Use 4 minutes ago to ensure all records are clearly within the 5-minute window
        window_start = datetime.now(UTC) - timedelta(minutes=4)
    return [
        SessionStateRecord(
            session_id="test-session",
            tool_name=tool_name,
            args={"record_id": f"rec-{i}"},
            decision=decision,
            created_at=window_start + timedelta(seconds=i * 10),
        )
        for i in range(count)
    ]


@pytest.mark.asyncio
class TestRateLimitRule:
    async def test_under_limit_allows(self, rule):
        history = _make_history(2)
        result = await rule.evaluate("delete_record", {"record_id": "rec-new"}, "test-session", history)
        assert result.passed is True
        assert result.rule_type == "stateful"

    async def test_at_limit_blocks(self, rule):
        history = _make_history(3)
        result = await rule.evaluate("delete_record", {"record_id": "rec-new"}, "test-session", history)
        assert result.passed is False
        assert "Rate limit exceeded" in result.reason

    async def test_over_limit_blocks(self, rule):
        history = _make_history(5)
        result = await rule.evaluate("delete_record", {"record_id": "rec-new"}, "test-session", history)
        assert result.passed is False

    async def test_empty_history_allows(self, rule):
        result = await rule.evaluate("delete_record", {"record_id": "rec-1"}, "test-session", [])
        assert result.passed is True

    async def test_only_allowed_calls_count(self, rule):
        # 2 ALLOWED + 2 BLOCKED = only 2 count toward limit
        history = _make_history(2, decision="ALLOW") + _make_history(2, decision="BLOCK")
        result = await rule.evaluate("delete_record", {"record_id": "rec-new"}, "test-session", history)
        assert result.passed is True  # 2 < 3

    async def test_expired_entries_not_counted(self, rule):
        # All entries outside the 300s window
        old_start = datetime.now(UTC) - timedelta(minutes=10)
        history = _make_history(5, window_start=old_start)
        result = await rule.evaluate("delete_record", {"record_id": "rec-new"}, "test-session", history)
        assert result.passed is True

    async def test_mixed_window_entries(self, rule):
        # 2 old (outside window) + 2 recent (inside window) = 2 count
        old_start = datetime.now(UTC) - timedelta(minutes=10)
        recent_start = datetime.now(UTC) - timedelta(minutes=2)
        history = _make_history(2, window_start=old_start) + _make_history(2, window_start=recent_start)
        result = await rule.evaluate("delete_record", {"record_id": "rec-new"}, "test-session", history)
        assert result.passed is True  # 2 < 3

    async def test_different_tool_not_counted(self, rule):
        history = _make_history(5, tool_name="send_email")
        result = await rule.evaluate("delete_record", {"record_id": "rec-new"}, "test-session", history)
        assert result.passed is True
