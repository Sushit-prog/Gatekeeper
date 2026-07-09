from uuid import uuid4

from sqlalchemy.ext.asyncio import AsyncSession

from gatekeeper.models.audit import AuditLog
from gatekeeper.models.requests import GateCheckRequest, GateDecision


async def log_decision(session: AsyncSession, request: GateCheckRequest, decision: GateDecision) -> str:
    """Write an audit record for a gate check decision.

    Returns the UUID of the created record as a string.
    """
    audit_id = uuid4()
    record = AuditLog(
        id=audit_id,
        session_id=request.session_id,
        tool_name=request.tool_name,
        args=request.args,
        agent_reasoning=request.agent_reasoning,
        decision=decision.decision,
        matched_rules=[r.model_dump() for r in decision.matched_rules],
        latency_ms=decision.latency_ms,
    )
    session.add(record)
    await session.commit()
    return str(audit_id)
