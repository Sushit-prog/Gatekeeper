from collections.abc import AsyncGenerator

import pytest
import pytest_asyncio
from httpx import ASGITransport, AsyncClient
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine
from sqlalchemy.pool import StaticPool

from gatekeeper.api.routes import set_engine, set_registry
from gatekeeper.audit.db import get_session
from gatekeeper.models.audit import Base
from gatekeeper.rules.registry import RuleRegistry


@pytest_asyncio.fixture
async def test_engine():
    engine = create_async_engine(
        "sqlite+aiosqlite://",
        connect_args={"check_same_thread": False},
        poolclass=StaticPool,
    )
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)
    yield engine
    await engine.dispose()


@pytest_asyncio.fixture
async def test_session(test_engine) -> AsyncGenerator[AsyncSession, None]:
    session_factory = async_sessionmaker(test_engine, expire_on_commit=False)
    async with session_factory() as session:
        yield session


@pytest_asyncio.fixture
async def client(test_engine, test_session):
    session_factory = async_sessionmaker(test_engine, expire_on_commit=False)

    async def override_get_session():
        yield test_session

    from gatekeeper.main import app

    # Remove lifespan tasks so tests don't try to connect to real Postgres
    app.router.lifespan_context = None

    app.dependency_overrides[get_session] = override_get_session
    registry = RuleRegistry("policies/policy_registry.yaml")
    set_registry(registry)
    from gatekeeper.rules.pydantic_engine import PydanticRuleEngine
    set_engine(PydanticRuleEngine(registry))

    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as c:
        yield c
    app.dependency_overrides.clear()
