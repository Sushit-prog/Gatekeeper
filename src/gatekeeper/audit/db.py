from collections.abc import AsyncGenerator
from contextlib import asynccontextmanager
from datetime import UTC, datetime, timedelta

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine

from gatekeeper.config import settings
from gatekeeper.models.audit import Base, SessionState
from gatekeeper.rules.base import SessionStateRecord

engine = create_async_engine(settings.database_url, echo=False)
async_session_factory = async_sessionmaker(engine, expire_on_commit=False)


async def get_session() -> AsyncGenerator[AsyncSession, None]:
    """FastAPI dependency — plain async generator, no decorator."""
    async with async_session_factory() as session:
        yield session


@asynccontextmanager
async def session_context() -> AsyncGenerator[AsyncSession, None]:
    """Standalone async context manager for scripts and non-FastAPI usage."""
    async with async_session_factory() as session:
        yield session


async def init_db() -> None:
    """Create all tables defined in models. Call on app startup."""
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)


def _ensure_aware(dt: datetime) -> datetime:
    """Ensure a datetime is timezone-aware (UTC). Handles naive datetimes from SQLite."""
    if dt.tzinfo is None:
        return dt.replace(tzinfo=UTC)
    return dt


def _rows_to_records(rows) -> list[SessionStateRecord]:
    return [
        SessionStateRecord(
            session_id=r.session_id,
            tool_name=r.tool_name,
            args=r.args,
            decision=r.decision,
            tags=r.tags,
            created_at=r.created_at,
        )
        for r in rows
    ]


async def fetch_session_history(
    session: AsyncSession,
    session_id: str,
    tool_name: str,
    window_seconds: int = 3600,
) -> list[SessionStateRecord]:
    """Fetch session state history for a given session_id and tool_name.

    Uses a single indexed query with composite index (session_id, tool_name, created_at).
    Returns records ordered by created_at ascending (oldest first).
    """
    cutoff = datetime.now(UTC) - timedelta(seconds=window_seconds)
    stmt = (
        select(SessionState)
        .where(SessionState.session_id == session_id)
        .where(SessionState.tool_name == tool_name)
        .where(SessionState.created_at >= cutoff)
        .order_by(SessionState.created_at.asc())
    )
    result = await session.execute(stmt)
    rows = result.scalars().all()
    return _rows_to_records(rows)


async def fetch_session_history_all_tools(
    session: AsyncSession,
    session_id: str,
    window_seconds: int = 3600,
) -> list[SessionStateRecord]:
    """Fetch ALL session state history for a session_id across all tools.

    Used by scope_creep rule to find protection tags from other tools.
    """
    cutoff = datetime.now(UTC) - timedelta(seconds=window_seconds)
    stmt = (
        select(SessionState)
        .where(SessionState.session_id == session_id)
        .where(SessionState.created_at >= cutoff)
        .order_by(SessionState.created_at.asc())
    )
    result = await session.execute(stmt)
    rows = result.scalars().all()
    return _rows_to_records(rows)
