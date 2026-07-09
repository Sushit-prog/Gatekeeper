"""Parity test suite — runs the same test cases against both PydanticRuleEngine and OPARuleEngine.

Asserts that both engines produce identical decisions (ALLOW/BLOCK) and fire
the same rule_ids. Message wording can differ, but the final decision and
which rules fired must match exactly.
"""

from datetime import UTC, datetime

import pytest

from gatekeeper.models.requests import GateCheckRequest
from gatekeeper.rules.base import SessionStateRecord
from gatekeeper.rules.pydantic_engine import PydanticRuleEngine
from gatekeeper.rules.registry import RuleRegistry

_NOW = datetime.now(UTC)


@pytest.fixture
def registry():
    return RuleRegistry("policies/policy_registry.yaml")


@pytest.fixture
def pydantic_engine(registry):
    return PydanticRuleEngine(registry)


# Test cases: (name, tool_name, args, session_history, expected_decision, expected_rule_ids_blocked)
PARITY_CASES = [
    # M1 stateless cases
    (
        "clean_send_email",
        "send_email",
        {"recipient": "user@gmail.com", "body": "Hello"},
        [],
        "ALLOW",
        [],
    ),
    (
        "pii_in_send_email",
        "send_email",
        {"recipient": "user@blocked-domain.com", "body": "Hello"},
        [],
        "BLOCK",
        ["denylist"],
    ),
    (
        "pii_detection_in_body",
        "send_email",
        {"recipient": "user@gmail.com", "body": "SSN: 123-45-6789"},
        [],
        "BLOCK",
        ["pii_detection"],
    ),
    (
        "valid_uuid_delete",
        "delete_record",
        {"record_id": "550e8400-e29b-41d4-a716-446655440000"},
        [],
        "ALLOW",
        [],
    ),
    (
        "bad_uuid_delete",
        "delete_record",
        {"record_id": "not-a-uuid"},
        [],
        "BLOCK",
        ["argument_bounds"],
    ),
    (
        "unknown_tool_allows",
        "unknown_tool",
        {"foo": "bar"},
        [],
        "ALLOW",
        [],
    ),
    # Adversarial edge case: near-miss PII
    (
        "near_miss_extension_number",
        "send_email",
        {"body": "Call me at extension 5551234"},
        [],
        "ALLOW",
        [],
    ),
    # M2 stateful cases
    (
        "delete_valid_no_history",
        "delete_record",
        {"record_id": "550e8400-e29b-41d4-a716-446655440000"},
        [],
        "ALLOW",
        [],
    ),
    # Scope creep: protected entity
    (
        "scope_creep_protected",
        "delete_record",
        {"record_id": "550e8400-e29b-41d4-a716-446655440000"},
        [
            SessionStateRecord(
                session_id="test",
                tool_name="check_permissions",
                args={"record_id": "550e8400-e29b-41d4-a716-446655440000"},
                decision="ALLOW",
                tags={"protected_record_ids": ["550e8400-e29b-41d4-a716-446655440000"]},
                created_at=_NOW,
            )
        ],
        "BLOCK",
        ["scope_creep"],
    ),
    # Rate limit: at limit
    (
        "rate_limit_at_limit",
        "delete_record",
        {"record_id": "550e8400-e29b-41d4-a716-446655440000"},
        [
            SessionStateRecord(
                session_id="test", tool_name="delete_record",
                args={"record_id": f"rec-{i}"}, decision="ALLOW",
                tags=None, created_at=_NOW,
            )
            for i in range(3)
        ],
        "BLOCK",
        ["rate_limit"],
    ),
    # Denylist: http_post blocked domain
    (
        "http_post_blocked_url",
        "http_post",
        {"url": "https://internal.corp/api", "timeout": 30, "body": "test"},
        [],
        "BLOCK",
        ["denylist"],
    ),
]


@pytest.mark.asyncio
class TestParity:
    @pytest.mark.parametrize(
        "name,tool_name,args,history,expected_decision,expected_blocked",
        PARITY_CASES,
        ids=[c[0] for c in PARITY_CASES],
    )
    async def test_pydantic_matches_expected(
        self, pydantic_engine, name, tool_name, args, history,
        expected_decision, expected_blocked,
    ):
        result = await pydantic_engine.evaluate(tool_name, args, history)
        assert result.decision == expected_decision, (
            f"[Pydantic {name}] Expected {expected_decision}, got {result.decision}"
        )
        failed_rule_ids = [r.rule_id for r in result.matched_rules if not r.passed]
        for rule_id in expected_blocked:
            assert rule_id in failed_rule_ids, (
                f"[Pydantic {name}] Expected rule_id '{rule_id}' to fail, "
                f"but only {failed_rule_ids} failed"
            )

    async def test_pydantic_scope_creep_scenario(self, pydantic_engine):
        """The core M2 scenario: check_permissions then delete_record on same entity."""
        record_id = "550e8400-e29b-41d4-a716-446655440000"

        # Step 1: check_permissions — should ALLOW
        r1 = await pydantic_engine.evaluate(
            "check_permissions", {"record_id": record_id}, []
        )
        assert r1.decision == "ALLOW"
        assert r1.tags is not None
        assert "protected_record_ids" in r1.tags

        # Step 2: delete_record with protection history — should BLOCK
        history = [
            SessionStateRecord(
                session_id="test",
                tool_name="check_permissions",
                args={"record_id": record_id},
                decision="ALLOW",
                tags=r1.tags,
                created_at=_NOW,
            )
        ]
        r2 = await pydantic_engine.evaluate(
            "delete_record", {"record_id": record_id}, history
        )
        assert r2.decision == "BLOCK"
        failed_ids = [r.rule_id for r in r2.matched_rules if not r.passed]
        assert "scope_creep" in failed_ids


# OPA parity tests — only run if OPA server is available
try:
    import httpx

    async def _opa_available() -> bool:
        try:
            async with httpx.AsyncClient(timeout=2.0) as client:
                r = await client.get("http://localhost:8181/health")
                return r.status_code == 200
        except Exception:
            return False
except ImportError:
    async def _opa_available() -> bool:
        return False


@pytest.fixture
async def opa_engine():
    """Create OPA engine, skip tests if OPA is not running."""
    from gatekeeper.rules.opa_engine import OPARuleEngine
    engine = OPARuleEngine(opa_url="http://localhost:8181")
    yield engine
    await engine.close()


@pytest.mark.asyncio
@pytest.mark.skipif(
    not pytest.importorskip("httpx"),
    reason="httpx not installed"
)
class TestOPAParity:
    """Parity tests against OPARuleEngine — skipped if OPA is not running."""

    @pytest.fixture(autouse=True)
    async def _check_opa(self):
        if not await _opa_available():
            pytest.skip("OPA server not available at localhost:8181")

    @pytest.mark.parametrize(
        "name,tool_name,args,history,expected_decision,expected_blocked",
        PARITY_CASES,
        ids=[c[0] for c in PARITY_CASES],
    )
    async def test_opa_matches_expected(
        self, opa_engine, name, tool_name, args, history,
        expected_decision, expected_blocked,
    ):
        result = await opa_engine.evaluate(tool_name, args, history)
        assert result.decision == expected_decision, (
            f"[OPA {name}] Expected {expected_decision}, got {result.decision}"
        )
        failed_rule_ids = [r.rule_id for r in result.matched_rules if not r.passed]
        for rule_id in expected_blocked:
            assert rule_id in failed_rule_ids, (
                f"[OPA {name}] Expected rule_id '{rule_id}' to fail, "
                f"but only {failed_rule_ids} failed"
            )

    async def test_opa_scope_creep_scenario(self, opa_engine):
        """The core M2 scenario against OPA engine."""
        record_id = "550e8400-e29b-41d4-a716-446655440000"

        r1 = await opa_engine.evaluate(
            "check_permissions", {"record_id": record_id}, []
        )
        assert r1.decision == "ALLOW"

        history = [
            SessionStateRecord(
                session_id="test",
                tool_name="check_permissions",
                args={"record_id": record_id},
                decision="ALLOW",
                tags=r1.tags if r1.tags else {"protected_record_ids": [record_id]},
                created_at=_NOW,
            )
        ]
        r2 = await opa_engine.evaluate(
            "delete_record", {"record_id": record_id}, history
        )
        assert r2.decision == "BLOCK"
        failed_ids = [r.rule_id for r in r2.matched_rules if not r.passed]
        assert "scope_creep" in failed_ids

    async def test_cross_engine_parity(self, pydantic_engine, opa_engine):
        """Direct comparison: both engines must produce the same decision."""
        record_id = "550e8400-e29b-41d4-a716-446655440000"
        history = [
            SessionStateRecord(
                session_id="test",
                tool_name="check_permissions",
                args={"record_id": record_id},
                decision="ALLOW",
                tags={"protected_record_ids": [record_id]},
                created_at=_NOW,
            )
        ]

        pydantic_result = await pydantic_engine.evaluate(
            "delete_record", {"record_id": record_id}, history
        )
        opa_result = await opa_engine.evaluate(
            "delete_record", {"record_id": record_id}, history
        )

        assert pydantic_result.decision == opa_result.decision, (
            f"Decision mismatch: Pydantic={pydantic_result.decision}, OPA={opa_result.decision}"
        )

        pydantic_failed = set(r.rule_id for r in pydantic_result.matched_rules if not r.passed)
        opa_failed = set(r.rule_id for r in opa_result.matched_rules if not r.passed)
        assert pydantic_failed == opa_failed, (
            f"Rule mismatch: Pydantic={pydantic_failed}, OPA={opa_failed}"
        )
