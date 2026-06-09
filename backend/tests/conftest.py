import pytest
import pytest_asyncio
from httpx import ASGITransport, AsyncClient
from sqlalchemy.ext.asyncio import AsyncEngine, AsyncSession, create_async_engine
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import NullPool

import app.db as db_module
from app.config import settings
from app.db import AsyncSessionLocal
from app.main import app
from app.routers.auth import limiter


@pytest.fixture(autouse=True)
def reset_rate_limiter():
    """Reset slowapi in-memory counters before each test to prevent cross-test rate limit bleed."""
    limiter.reset()
    yield


@pytest.fixture(scope="session", autouse=True)
def use_nullpool_engine():
    """Replace the global SQLAlchemy engine with a NullPool variant for the entire test session.

    NullPool avoids asyncpg background cleanup tasks that trigger
    'Event loop is closed' RuntimeError when multiple tests each get a fresh
    asyncio event loop (pytest-asyncio default behaviour).
    """
    test_engine = create_async_engine(settings.database_url, poolclass=NullPool)
    test_session_local = sessionmaker(test_engine, class_=AsyncSession, expire_on_commit=False)

    # Patch the global engine and session factory used by FastAPI dependencies
    original_engine = db_module.engine
    original_session_local = db_module.AsyncSessionLocal

    db_module.engine = test_engine
    db_module.AsyncSessionLocal = test_session_local

    yield

    # Restore originals (though in pytest this barely matters)
    db_module.engine = original_engine
    db_module.AsyncSessionLocal = original_session_local


@pytest_asyncio.fixture(scope="session")
async def client():
    async with AsyncClient(
        transport=ASGITransport(app=app), base_url="http://test"
    ) as ac:
        yield ac


@pytest_asyncio.fixture(scope="session")
async def auth_client():
    """Session-scoped HTTP client for auth integration tests.

    Session-scope reuses the connection across tests.
    Uniqueness of test data is enforced by using uuid-suffixed email addresses in each test.
    """
    async with AsyncClient(
        transport=ASGITransport(app=app), base_url="http://test"
    ) as ac:
        yield ac


@pytest_asyncio.fixture
async def db_session() -> AsyncSession:
    """Function-scoped async DB session that rolls back after each test to avoid state leak."""
    async with AsyncSessionLocal() as session:
        async with session.begin():
            yield session
            await session.rollback()
