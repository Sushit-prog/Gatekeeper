"""Audit log query functions for the Streamlit dashboard.

Creates a FRESH async engine per asyncio.run() call to avoid event-loop
binding issues with asyncpg. Each function creates its own engine, runs
the query, and disposes the engine before returning.
"""

import asyncio
import json
import random
from datetime import UTC, datetime, timedelta

import pandas as pd
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine
from sqlalchemy.pool import NullPool

from gatekeeper.config import settings
from gatekeeper.models.audit import AuditLog


def _run_async(coro):
    """Run an async coroutine from Streamlit's sync context."""
    return asyncio.run(coro)


def _make_session_factory():
    """Create a fresh engine + session factory for this call.

    Uses NullPool to avoid asyncpg connection state issues across
    asyncio.run()'s per-rerun event loops. Each session gets a
    genuinely fresh connection that closes fully on dispose.
    """
    engine = create_async_engine(settings.database_url, echo=False, poolclass=NullPool)
    factory = async_sessionmaker(engine, expire_on_commit=False)
    return engine, factory


async def _get_total_checks(session: AsyncSession) -> int:
    result = await session.execute(select(func.count()).select_from(AuditLog))
    return result.scalar() or 0


async def _get_checks_last_24h(session: AsyncSession) -> int:
    cutoff = datetime.now(UTC) - timedelta(hours=24)
    result = await session.execute(
        select(func.count()).select_from(AuditLog).where(AuditLog.created_at >= cutoff)
    )
    return result.scalar() or 0


async def _get_block_rate_over_time(session: AsyncSession, hours: int = 24) -> pd.DataFrame:
    cutoff = datetime.now(UTC) - timedelta(hours=hours)
    result = await session.execute(
        select(AuditLog.created_at, AuditLog.decision)
        .where(AuditLog.created_at >= cutoff)
        .order_by(AuditLog.created_at.asc())
    )
    rows = result.all()
    if not rows:
        return pd.DataFrame(columns=["time", "decision"])

    df = pd.DataFrame(rows, columns=["time", "decision"])
    df["time"] = pd.to_datetime(df["time"])
    df["hour"] = df["time"].dt.floor("h")
    pivot = df.groupby(["hour", "decision"]).size().unstack(fill_value=0)
    if "ALLOW" not in pivot.columns:
        pivot["ALLOW"] = 0
    if "BLOCK" not in pivot.columns:
        pivot["BLOCK"] = 0
    return pivot[["ALLOW", "BLOCK"]]


async def _get_block_count_by_rule(session: AsyncSession) -> pd.DataFrame:
    result = await session.execute(
        select(AuditLog.matched_rules, AuditLog.created_at)
        .where(AuditLog.decision == "BLOCK")
        .order_by(AuditLog.created_at.desc())
    )
    rows = result.all()
    if not rows:
        return pd.DataFrame(columns=["rule_id", "count"])

    rule_counts: dict[str, int] = {}
    for matched_rules, _ in rows:
        if isinstance(matched_rules, str):
            matched_rules = json.loads(matched_rules)
        for rule in matched_rules:
            if isinstance(rule, dict) and not rule.get("passed", True):
                rule_id = rule.get("rule_id", "unknown")
                rule_counts[rule_id] = rule_counts.get(rule_id, 0) + 1

    df = pd.DataFrame(list(rule_counts.items()), columns=["rule_id", "count"])
    return df.sort_values("count", ascending=False)


async def _get_recent_blocks(session: AsyncSession, limit: int = 20) -> list[dict]:
    result = await session.execute(
        select(AuditLog)
        .where(AuditLog.decision == "BLOCK")
        .order_by(AuditLog.created_at.desc())
        .limit(limit)
    )
    rows = result.scalars().all()
    return [
        {
            "id": str(r.id),
            "tool_name": r.tool_name,
            "args": r.args,
            "decision": r.decision,
            "matched_rules": r.matched_rules,
            "latency_ms": r.latency_ms,
            "created_at": r.created_at.isoformat() if r.created_at else None,
        }
        for r in rows
    ]


async def _get_random_blocks(session: AsyncSession, n: int = 10) -> list[dict]:
    result = await session.execute(
        select(AuditLog).where(AuditLog.decision == "BLOCK")
    )
    rows = result.scalars().all()
    if not rows:
        return []
    sampled = random.sample(list(rows), min(n, len(rows)))
    return [
        {
            "id": str(r.id),
            "tool_name": r.tool_name,
            "args": r.args,
            "matched_rules": r.matched_rules,
            "created_at": r.created_at.isoformat() if r.created_at else None,
        }
        for r in sampled
    ]


async def _get_engine_backend(session: AsyncSession) -> str:
    return settings.engine_backend


async def _submit_review(session: AsyncSession, audit_id: str, marked_fp: bool, note: str | None) -> None:
    from dashboard.models import HumanReview
    review = HumanReview(
        audit_id=audit_id,
        marked_fp=marked_fp,
        reviewer_note=note,
    )
    session.add(review)
    await session.commit()


async def _get_review_stats(session: AsyncSession) -> dict:
    from dashboard.models import HumanReview
    total = await session.execute(select(func.count()).select_from(HumanReview))
    fp_count = await session.execute(
        select(func.count()).select_from(HumanReview).where(HumanReview.marked_fp == True)
    )
    total_reviewed = total.scalar() or 0
    fp_count_val = fp_count.scalar() or 0
    fp_rate = (fp_count_val / total_reviewed * 100) if total_reviewed > 0 else 0.0
    return {
        "total_reviewed": total_reviewed,
        "false_positives": fp_count_val,
        "fp_rate": fp_rate,
    }


# Sync wrappers for Streamlit — each creates a fresh engine per call

def get_total_checks() -> int:
    async def _query():
        engine, factory = _make_session_factory()
        try:
            async with factory() as session:
                return await _get_total_checks(session)
        finally:
            await engine.dispose()
    return _run_async(_query())


def get_checks_last_24h() -> int:
    async def _query():
        engine, factory = _make_session_factory()
        try:
            async with factory() as session:
                return await _get_checks_last_24h(session)
        finally:
            await engine.dispose()
    return _run_async(_query())


def get_block_rate_over_time(hours: int = 24) -> pd.DataFrame:
    async def _query():
        engine, factory = _make_session_factory()
        try:
            async with factory() as session:
                return await _get_block_rate_over_time(session, hours)
        finally:
            await engine.dispose()
    return _run_async(_query())


def get_block_count_by_rule() -> pd.DataFrame:
    async def _query():
        engine, factory = _make_session_factory()
        try:
            async with factory() as session:
                return await _get_block_count_by_rule(session)
        finally:
            await engine.dispose()
    return _run_async(_query())


def get_recent_blocks(limit: int = 20) -> list[dict]:
    async def _query():
        engine, factory = _make_session_factory()
        try:
            async with factory() as session:
                return await _get_recent_blocks(session, limit)
        finally:
            await engine.dispose()
    return _run_async(_query())


def get_random_blocks(n: int = 10) -> list[dict]:
    async def _query():
        engine, factory = _make_session_factory()
        try:
            async with factory() as session:
                return await _get_random_blocks(session, n)
        finally:
            await engine.dispose()
    return _run_async(_query())


def get_engine_backend() -> str:
    async def _query():
        engine, factory = _make_session_factory()
        try:
            async with factory() as session:
                return await _get_engine_backend(session)
        finally:
            await engine.dispose()
    return _run_async(_query())


def submit_review(audit_id: str, marked_fp: bool, note: str | None = None) -> None:
    async def _query():
        engine, factory = _make_session_factory()
        try:
            async with factory() as session:
                await _submit_review(session, audit_id, marked_fp, note)
        finally:
            await engine.dispose()
    _run_async(_query())


def get_review_stats() -> dict:
    async def _query():
        engine, factory = _make_session_factory()
        try:
            async with factory() as session:
                return await _get_review_stats(session)
        finally:
            await engine.dispose()
    return _run_async(_query())
