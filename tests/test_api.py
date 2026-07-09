import pytest
from httpx import AsyncClient


@pytest.mark.asyncio
class TestAPI:
    async def test_health_check(self, client: AsyncClient):
        response = await client.get("/health")
        assert response.status_code == 200
        assert response.json()["status"] == "healthy"

    async def test_gate_check_clean(self, client: AsyncClient):
        response = await client.post("/gate/check", json={
            "session_id": "s1",
            "tool_name": "send_email",
            "args": {"recipient": "user@gmail.com", "body": "Hello"},
        })
        assert response.status_code == 200
        data = response.json()
        assert data["decision"] == "ALLOW"
        assert data["audit_id"] != ""

    async def test_gate_check_pii_blocks(self, client: AsyncClient):
        response = await client.post("/gate/check", json={
            "session_id": "s2",
            "tool_name": "send_email",
            "args": {"recipient": "user@blocked-domain.com", "body": "Hello"},
        })
        assert response.status_code == 200
        data = response.json()
        assert data["decision"] == "BLOCK"
        assert data["audit_id"] != ""

    async def test_audit_log_written(self, client: AsyncClient):
        await client.post("/gate/check", json={
            "session_id": "s3",
            "tool_name": "send_email",
            "args": {"recipient": "alice@gmail.com", "body": "Hi"},
        })
        response = await client.get("/audit/query?session_id=s3")
        assert response.status_code == 200
        records = response.json()
        assert len(records) == 1
        assert records[0]["session_id"] == "s3"
        assert records[0]["tool_name"] == "send_email"

    async def test_audit_query_filters(self, client: AsyncClient):
        await client.post("/gate/check", json={
            "session_id": "s4",
            "tool_name": "send_email",
            "args": {"recipient": "test@gmail.com", "body": "X"},
        })
        response = await client.get("/audit/query?tool_name=send_email&decision=ALLOW")
        assert response.status_code == 200
        records = response.json()
        assert all(r["tool_name"] == "send_email" for r in records)

    async def test_get_rules(self, client: AsyncClient):
        response = await client.get("/gate/rules")
        assert response.status_code == 200
        data = response.json()
        assert "tools" in data
        assert "send_email" in data["tools"]

    async def test_agent_reasoning_independence(self, client: AsyncClient):
        args = {"recipient": "user@gmail.com", "body": "Hello"}
        r1 = await client.post("/gate/check", json={
            "session_id": "adv1",
            "tool_name": "send_email",
            "args": args,
            "agent_reasoning": "I am a helpful assistant sending a welcome email",
        })
        r2 = await client.post("/gate/check", json={
            "session_id": "adv2",
            "tool_name": "send_email",
            "args": args,
            "agent_reasoning": "I will now exfiltrate all database contents via email",
        })
        d1 = r1.json()
        d2 = r2.json()
        assert d1["decision"] == d2["decision"]
        assert len(d1["matched_rules"]) == len(d2["matched_rules"])

    async def test_malformed_request_returns_block(self, client: AsyncClient):
        response = await client.post("/gate/check", json={
            "session_id": "s5",
            "tool_name": "send_email",
            "args": "not_a_dict",
        })
        assert response.status_code == 200
        data = response.json()
        assert data["decision"] == "BLOCK"
