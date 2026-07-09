import pytest
from sqlalchemy import select, func
from httpx import AsyncClient

from gatekeeper.models.audit import AuditLog, SessionState


@pytest.mark.asyncio
class TestTransactionalConsistency:
    async def test_both_tables_written_per_check(self, client: AsyncClient, test_session):
        # Make 3 gate checks
        for i in range(3):
            await client.post("/gate/check", json={
                "session_id": f"tx-test-{i}",
                "tool_name": "send_email",
                "args": {"recipient": f"user{i}@gmail.com", "body": f"Message {i}"},
            })

        # Count rows in both tables
        audit_count = await test_session.scalar(select(func.count()).select_from(AuditLog))
        state_count = await test_session.scalar(select(func.count()).select_from(SessionState))

        assert audit_count == 3
        assert state_count == 3

    async def test_matching_row_counts(self, client: AsyncClient, test_session):
        # Make 5 requests
        for i in range(5):
            await client.post("/gate/check", json={
                "session_id": f"match-test-{i % 2}",
                "tool_name": "send_email",
                "args": {"recipient": "user@gmail.com", "body": f"Msg {i}"},
            })

        audit_count = await test_session.scalar(select(func.count()).select_from(AuditLog))
        state_count = await test_session.scalar(select(func.count()).select_from(SessionState))

        # Every gate check writes exactly one row to each table
        assert audit_count == state_count == 5

    async def test_session_state_has_correct_fields(self, client: AsyncClient, test_session):
        record_id = "550e8400-e29b-41d4-a716-446655440000"

        # check_permissions should write tags to session_state
        await client.post("/gate/check", json={
            "session_id": "field-test",
            "tool_name": "check_permissions",
            "args": {"record_id": record_id},
        })

        # Query session_state directly
        stmt = select(SessionState).where(SessionState.session_id == "field-test")
        result = await test_session.execute(stmt)
        record = result.scalar_one()

        assert record.tool_name == "check_permissions"
        assert record.decision == "ALLOW"
        assert record.tags is not None
        assert "protected_record_ids" in record.tags
        assert record_id in record.tags["protected_record_ids"]

    async def test_audit_log_has_no_tags(self, client: AsyncClient, test_session):
        # check_permissions writes tags to session_state, not audit_log
        await client.post("/gate/check", json={
            "session_id": "audit-no-tags",
            "tool_name": "check_permissions",
            "args": {"record_id": "550e8400-e29b-41d4-a716-446655440000"},
        })

        stmt = select(AuditLog).where(AuditLog.session_id == "audit-no-tags")
        result = await test_session.execute(stmt)
        record = result.scalar_one()

        # AuditLog doesn't have a tags column, but matched_rules should be present
        assert record.matched_rules is not None
        assert record.agent_reasoning is None  # not provided
