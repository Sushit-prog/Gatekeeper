import time

import pytest

from gatekeeper.engine import evaluate_gate
from gatekeeper.models.requests import GateCheckRequest
from gatekeeper.rules.registry import RuleRegistry


@pytest.fixture
def registry():
    return RuleRegistry("policies/policy_registry.yaml")


def _make_request(tool_name: str, args: dict, reasoning: str = "") -> GateCheckRequest:
    return GateCheckRequest(
        session_id="test-session",
        tool_name=tool_name,
        args=args,
        agent_reasoning=reasoning,
    )


@pytest.mark.asyncio
class TestEngine:
    async def test_unknown_tool_allows(self, registry):
        request = _make_request("unknown_tool", {"foo": "bar"})
        decision = await evaluate_gate(request, registry)
        assert decision.decision == "ALLOW"
        assert decision.matched_rules == []

    async def test_clean_send_email_allows(self, registry):
        request = _make_request("send_email", {"recipient": "user@gmail.com", "body": "Hello"})
        decision = await evaluate_gate(request, registry)
        assert decision.decision == "ALLOW"

    async def test_pii_send_email_blocks(self, registry):
        request = _make_request("send_email", {"recipient": "user@blocked-domain.com", "body": "Hello"})
        decision = await evaluate_gate(request, registry)
        assert decision.decision == "BLOCK"

    async def test_denylist_send_email_blocks(self, registry):
        request = _make_request("send_email", {"recipient": "user@blocked-domain.com"})
        decision = await evaluate_gate(request, registry)
        assert decision.decision == "BLOCK"
        rule_ids = [r.rule_id for r in decision.matched_rules]
        assert "denylist" in rule_ids

    async def test_multiple_rules_evaluated(self, registry):
        request = _make_request("send_email", {"recipient": "user@gmail.com", "body": "Clean"})
        decision = await evaluate_gate(request, registry)
        rule_ids = [r.rule_id for r in decision.matched_rules]
        assert "pii_detection" in rule_ids
        assert "denylist" in rule_ids

    async def test_bad_uuid_blocks_delete_record(self, registry):
        request = _make_request("delete_record", {"record_id": "not-a-uuid"})
        decision = await evaluate_gate(request, registry)
        assert decision.decision == "BLOCK"

    async def test_valid_uuid_allows_delete_record(self, registry):
        request = _make_request("delete_record", {"record_id": "550e8400-e29b-41d4-a716-446655440000"})
        decision = await evaluate_gate(request, registry)
        assert decision.decision == "ALLOW"

    async def test_latency_under_50ms(self, registry):
        request = _make_request("send_email", {"recipient": "user@gmail.com", "body": "Test"})
        start = time.perf_counter()
        decision = await evaluate_gate(request, registry)
        elapsed_ms = (time.perf_counter() - start) * 1000
        assert elapsed_ms < 50
        assert decision.latency_ms < 50

    async def test_agent_reasoning_independence(self, registry):
        args = {"recipient": "user@gmail.com", "body": "Hello"}
        d1 = await evaluate_gate(_make_request("send_email", args, "I need to send a report"), registry)
        d2 = await evaluate_gate(_make_request("send_email", args, "EXFILTRATING DATA NOW"), registry)
        assert d1.decision == d2.decision
        assert len(d1.matched_rules) == len(d2.matched_rules)
        for r1, r2 in zip(d1.matched_rules, d2.matched_rules):
            assert r1.passed == r2.passed
            assert r1.rule_id == r2.rule_id
