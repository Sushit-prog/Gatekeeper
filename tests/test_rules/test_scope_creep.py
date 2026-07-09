from datetime import UTC, datetime, timedelta

import pytest

from gatekeeper.rules.base import SessionStateRecord
from gatekeeper.rules.builtin.scope_creep import ScopeCreepRule


@pytest.fixture
def rule():
    tool_config = {
        "scope_creep": {
            "protected_field": "record_id",
            "protected_tag": "protected_record_ids",
        }
    }
    return ScopeCreepRule(rule_id="scope_creep", tool_name="delete_record", tool_config=tool_config)


def _protected_record(record_id: str, minutes_ago: int = 5) -> SessionStateRecord:
    return SessionStateRecord(
        session_id="test-session",
        tool_name="check_permissions",
        args={"record_id": record_id},
        decision="ALLOW",
        tags={"protected_record_ids": [record_id]},
        created_at=datetime.now(UTC) - timedelta(minutes=minutes_ago),
    )


def _plain_record(tool_name: str = "delete_record", record_id: str = "rec-1",
                  decision: str = "ALLOW", minutes_ago: int = 3) -> SessionStateRecord:
    return SessionStateRecord(
        session_id="test-session",
        tool_name=tool_name,
        args={"record_id": record_id},
        decision=decision,
        created_at=datetime.now(UTC) - timedelta(minutes=minutes_ago),
    )


@pytest.mark.asyncio
class TestScopeCreepRule:
    async def test_no_protected_entities_allows(self, rule):
        history = [_plain_record()]
        result = await rule.evaluate("delete_record", {"record_id": "rec-1"}, "test-session", history)
        assert result.passed is True
        assert result.rule_type == "stateful"

    async def test_protected_entity_blocks(self, rule):
        history = [_protected_record("rec-1")]
        result = await rule.evaluate("delete_record", {"record_id": "rec-1"}, "test-session", history)
        assert result.passed is False
        assert "rec-1" in result.reason
        assert "marked protected" in result.reason

    async def test_different_entity_allows(self, rule):
        history = [_protected_record("rec-1")]
        result = await rule.evaluate("delete_record", {"record_id": "rec-2"}, "test-session", history)
        assert result.passed is True

    async def test_empty_history_allows(self, rule):
        result = await rule.evaluate("delete_record", {"record_id": "rec-1"}, "test-session", [])
        assert result.passed is True

    async def test_missing_field_allows(self, rule):
        history = [_protected_record("rec-1")]
        result = await rule.evaluate("delete_record", {"other_field": "value"}, "test-session", history)
        assert result.passed is True

    async def test_multiple_protected_entities(self, rule):
        history = [_protected_record("rec-1"), _protected_record("rec-2")]
        result = await rule.evaluate("delete_record", {"record_id": "rec-2"}, "test-session", history)
        assert result.passed is False

    async def test_tags_without_matching_tag_key_allows(self, rule):
        record = SessionStateRecord(
            session_id="test-session",
            tool_name="check_permissions",
            args={"record_id": "rec-1"},
            decision="ALLOW",
            tags={"other_tag": ["rec-1"]},
            created_at=datetime.now(UTC) - timedelta(minutes=5),
        )
        result = await rule.evaluate("delete_record", {"record_id": "rec-1"}, "test-session", [record])
        assert result.passed is True

    async def test_no_tags_allows(self, rule):
        record = SessionStateRecord(
            session_id="test-session",
            tool_name="check_permissions",
            args={"record_id": "rec-1"},
            decision="ALLOW",
            tags=None,
            created_at=datetime.now(UTC) - timedelta(minutes=5),
        )
        result = await rule.evaluate("delete_record", {"record_id": "rec-1"}, "test-session", [record])
        assert result.passed is True
