import pytest
from httpx import ASGITransport, AsyncClient
from sqlalchemy.ext.asyncio import AsyncSession

from app.db import AsyncSessionLocal
from app.main import app


@pytest.fixture(scope="session")
async def client():
    async with AsyncClient(
        transport=ASGITransport(app=app), base_url="http://test"
    ) as ac:
        yield ac


@pytest.fixture
async def db_session() -> AsyncSession:
    """Function-scoped async DB session that rolls back after each test to avoid state leak."""
    async with AsyncSessionLocal() as session:
        async with session.begin():
            yield session
            await session.rollback()
