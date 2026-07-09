"""Prune old session_state records.

Usage:
    python scripts/prune_session_state.py

Environment variables:
    DATABASE_URL: PostgreSQL connection string (default: postgresql+asyncpg://gatekeeper:gatekeeper@localhost:5432/gatekeeper)
    SESSION_STATE_TTL_HOURS: Hours to retain records (default: 24)
"""

import asyncio
import os
from datetime import UTC, datetime, timedelta

from sqlalchemy import delete, text
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine

DATABASE_URL = os.getenv(
    "DATABASE_URL",
    "postgresql+asyncpg://gatekeeper:gatekeeper@localhost:5432/gatekeeper",
)
TTL_HOURS = int(os.getenv("SESSION_STATE_TTL_HOURS", "24"))


async def prune() -> None:
    engine = create_async_engine(DATABASE_URL, echo=False)
    session_factory = async_sessionmaker(engine, expire_on_commit=False)

    cutoff = datetime.now(UTC) - timedelta(hours=TTL_HOURS)

    async with session_factory() as session:
        # Use raw delete for efficiency
        from gatekeeper.models.audit import SessionState

        stmt = delete(SessionState).where(SessionState.created_at < cutoff)
        result = await session.execute(stmt)
        await session.commit()
        deleted = result.rowcount

    await engine.dispose()
    print(f"Pruned {deleted} session_state records older than {TTL_HOURS}h (cutoff: {cutoff.isoformat()})")


if __name__ == "__main__":
    asyncio.run(prune())
