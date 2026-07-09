import pytest
from httpx import AsyncClient


@pytest.mark.asyncio
class TestAPIStateful:
    async def test_check_permissions_tags_record(self, client: AsyncClient):
        record_id = "550e8400-e29b-41d4-a716-446655440000"
        response = await client.post("/gate/check", json={
            "session_id": "scope-api-test",
            "tool_name": "check_permissions",
            "args": {"record_id": record_id},
        })
        assert response.status_code == 200
        data = response.json()
        assert data["decision"] == "ALLOW"
        assert data["tags"] is not None
        assert "protected_record_ids" in data["tags"]
        assert record_id in data["tags"]["protected_record_ids"]

    async def test_scope_creep_blocks_via_api(self, client: AsyncClient):
        record_id = "550e8400-e29b-41d4-a716-446655440000"
        session_id = "scope-api-full"

        # Step 1: check_permissions tags the record
        r1 = await client.post("/gate/check", json={
            "session_id": session_id,
            "tool_name": "check_permissions",
            "args": {"record_id": record_id},
        })
        assert r1.json()["decision"] == "ALLOW"

        # Step 2: delete_record on same record should be BLOCKED
        r2 = await client.post("/gate/check", json={
            "session_id": session_id,
            "tool_name": "delete_record",
            "args": {"record_id": record_id},
        })
        data = r2.json()
        assert data["decision"] == "BLOCK"
        rule_ids = [r["rule_id"] for r in data["matched_rules"] if not r["passed"]]
        assert "scope_creep" in rule_ids

    async def test_rate_limit_blocks_nth_call(self, client: AsyncClient):
        session_id = "rate-api-test"
        record_id = "550e8400-e29b-41d4-a716-446655440000"

        # Make 3 allowed calls
        for i in range(3):
            r = await client.post("/gate/check", json={
                "session_id": session_id,
                "tool_name": "delete_record",
                "args": {"record_id": record_id},
            })
            assert r.json()["decision"] == "ALLOW", f"Call {i+1} should be ALLOW"

        # 4th call should be BLOCKED
        r = await client.post("/gate/check", json={
            "session_id": session_id,
            "tool_name": "delete_record",
            "args": {"record_id": record_id},
        })
        data = r.json()
        assert data["decision"] == "BLOCK"
        rule_ids = [r["rule_id"] for r in data["matched_rules"] if not r["passed"]]
        assert "rate_limit" in rule_ids

    async def test_session_state_written_on_every_check(self, client: AsyncClient):
        # Make a request
        await client.post("/gate/check", json={
            "session_id": "ss-write-test",
            "tool_name": "send_email",
            "args": {"recipient": "user@gmail.com", "body": "Hello"},
        })

        # Verify session_state was written by checking audit_log has a row
        # (session_state is written in same transaction)
        r = await client.get("/audit/query?session_id=ss-write-test")
        assert r.status_code == 200
        records = r.json()
        assert len(records) == 1

    async def test_stateful_rules_appear_in_matched_rules(self, client: AsyncClient):
        record_id = "550e8400-e29b-41d4-a716-446655440000"
        response = await client.post("/gate/check", json={
            "session_id": "stateful-display",
            "tool_name": "delete_record",
            "args": {"record_id": record_id},
        })
        data = response.json()
        rule_types = set(r["rule_type"] for r in data["matched_rules"])
        assert "stateless" in rule_types
        assert "stateful" in rule_types
