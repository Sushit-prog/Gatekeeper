import time

import pytest
from sqlalchemy.ext.asyncio import AsyncSession

from gatekeeper.audit.db import fetch_session_history
from gatekeeper.engine import evaluate_gate
from gatekeeper.models.audit import SessionState
from gatekeeper.models.requests import GateCheckRequest
from gatekeeper.rules.registry import RuleRegistry


@pytest.fixture
def registry():
    return RuleRegistry("policies/policy_registry.yaml")


def _make_request(tool_name: str, args: dict, session_id: str = "test-session",
                  reasoning: str = "") -> GateCheckRequest:
    return GateCheckRequest(
        session_id=session_id,
        tool_name=tool_name,
        args=args,
        agent_reasoning=reasoning,
    )


@pytest.mark.asyncio
class TestEngineStateful:
    async def test_stateful_rules_run_with_session(self, registry, test_session):
        request = _make_request("delete_record", {"record_id": "550e8400-e29b-41d4-a716-446655440000"})
        decision = await evaluate_gate(request, registry, test_session)
        assert decision.decision == "ALLOW"
        rule_types = [r.rule_type for r in decision.matched_rules]
        assert "stateless" in rule_types
        assert "stateful" in rule_types

    async def test_rate_limit_triggers_after_n_calls(self, registry, test_session):
        session_id = "rate-test"
        record_id = "550e8400-e29b-41d4-a716-446655440000"

        # Make 3 allowed calls (the limit)
        for i in range(3):
            r = _make_request("delete_record", {"record_id": record_id}, session_id)
            d = await evaluate_gate(r, registry, test_session)
            assert d.decision == "ALLOW", f"Call {i+1} should be ALLOW"
            # Write session state manually (simulating what routes.py does)
            ss = SessionState(
                session_id=session_id,
                tool_name="delete_record",
                args={"record_id": record_id},
                decision="ALLOW",
            )
            test_session.add(ss)
        await test_session.commit()

        # 4th call should be BLOCKED by rate limit
        r = _make_request("delete_record", {"record_id": record_id}, session_id)
        d = await evaluate_gate(r, registry, test_session)
        assert d.decision == "BLOCK"
        rule_ids = [r.rule_id for r in d.matched_rules if not r.passed]
        assert "rate_limit" in rule_ids

    async def test_scope_creep_blocks_protected_entity(self, registry, test_session):
        session_id = "scope-test"
        record_id = "550e8400-e29b-41d4-a716-446655440000"

        # check_permissions tags record as protected
        r1 = _make_request("check_permissions", {"record_id": record_id}, session_id)
        d1 = await evaluate_gate(r1, registry, test_session)
        assert d1.decision == "ALLOW"

        # Write session state with protection tag
        ss = SessionState(
            session_id=session_id,
            tool_name="check_permissions",
            args={"record_id": record_id},
            decision="ALLOW",
            tags=d1.tags,
        )
        test_session.add(ss)
        await test_session.commit()

        # delete_record on the same record should be BLOCKED
        r2 = _make_request("delete_record", {"record_id": record_id}, session_id)
        d2 = await evaluate_gate(r2, registry, test_session)
        assert d2.decision == "BLOCK"
        rule_ids = [r.rule_id for r in d2.matched_rules if not r.passed]
        assert "scope_creep" in rule_ids

    async def test_latency_under_100ms(self, registry, test_session):
        request = _make_request("delete_record", {"record_id": "550e8400-e29b-41d4-a716-446655440000"})
        start = time.perf_counter()
        decision = await evaluate_gate(request, registry, test_session)
        elapsed_ms = (time.perf_counter() - start) * 1000
        assert elapsed_ms < 100
        assert decision.latency_ms < 100

    async def test_mixed_stateless_stateful_results(self, registry, test_session):
        request = _make_request("delete_record", {"record_id": "not-a-uuid"})
        decision = await evaluate_gate(request, registry, test_session)
        assert decision.decision == "BLOCK"
        # Should have both stateless (argument_bounds) and stateful (rate_limit, scope_creep) results
        stateless = [r for r in decision.matched_rules if r.rule_type == "stateless"]
        stateful = [r for r in decision.matched_rules if r.rule_type == "stateful"]
        assert len(stateless) >= 1
        assert len(stateful) >= 2
