from collections.abc import AsyncGenerator

import structlog
from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy import select, text
from sqlalchemy.ext.asyncio import AsyncSession

from gatekeeper.audit.db import get_session
from gatekeeper.audit.logger import log_decision, log_session_state
from gatekeeper.engine import evaluate_gate
from gatekeeper.models.audit import AuditLog
from gatekeeper.models.requests import GateCheckRequest, GateDecision
from gatekeeper.rules.registry import RuleRegistry

logger = structlog.get_logger()

router = APIRouter()

_registry: RuleRegistry | None = None


def set_registry(registry: RuleRegistry) -> None:
    global _registry
    _registry = registry


@router.post("/gate/check", response_model=GateDecision)
async def gate_check(
    request: GateCheckRequest,
    session: AsyncSession = Depends(get_session),
) -> GateDecision:
    """Validate a tool call against policy rules and log the decision."""
    try:
        decision = await evaluate_gate(request, _registry, session)
    except Exception as e:
        logger.error("rule_evaluation_error", error=str(e))
        return GateDecision(
            decision="BLOCK",
            matched_rules=[],
            latency_ms=0.0,
            audit_id="",
        )

    # Write both audit_log and session_state in the same transaction
    audit_id = await log_decision(session, request, decision)
    await log_session_state(session, request, decision, tags=decision.tags)
    await session.commit()

    decision.audit_id = audit_id

    logger.info(
        "gate_check",
        session_id=request.session_id,
        tool_name=request.tool_name,
        decision=decision.decision,
        audit_id=audit_id,
    )

    return decision


@router.get("/gate/rules")
async def get_rules() -> dict:
    """Return the currently loaded policy registry."""
    return _registry.get_policy_config()


@router.get("/audit/query")
async def query_audit(
    session_id: str | None = Query(default=None),
    tool_name: str | None = Query(default=None),
    decision: str | None = Query(default=None),
    limit: int = Query(default=50, le=200),
    session: AsyncSession = Depends(get_session),
) -> list[dict]:
    """Query audit log records with optional filters."""
    stmt = select(AuditLog)

    if session_id:
        stmt = stmt.where(AuditLog.session_id == session_id)
    if tool_name:
        stmt = stmt.where(AuditLog.tool_name == tool_name)
    if decision:
        stmt = stmt.where(AuditLog.decision == decision)

    stmt = stmt.order_by(AuditLog.created_at.desc()).limit(limit)
    result = await session.execute(stmt)
    records = result.scalars().all()

    return [
        {
            "id": str(r.id),
            "session_id": r.session_id,
            "tool_name": r.tool_name,
            "args": r.args,
            "agent_reasoning": r.agent_reasoning,
            "decision": r.decision,
            "matched_rules": r.matched_rules,
            "latency_ms": r.latency_ms,
            "created_at": r.created_at.isoformat() if r.created_at else None,
        }
        for r in records
    ]


@router.get("/health")
async def health(session: AsyncSession = Depends(get_session)) -> dict:
    """Liveness check including DB connectivity."""
    try:
        await session.execute(text("SELECT 1"))
        return {"status": "healthy"}
    except Exception as e:
        logger.error("health_check_failed", error=str(e))
        raise HTTPException(status_code=503, detail="Service unhealthy")
