from collections.abc import AsyncGenerator
from unittest.mock import AsyncMock, MagicMock

import pytest
from httpx import ASGITransport, AsyncClient

from app.database import get_db
from app.dependencies import verify_api_key
from app.main import app
from app.settings import settings

TEST_API_KEY = settings.market_data_internal_api_key


@pytest.fixture()
def auth_headers() -> dict[str, str]:
    """Headers with a valid Bearer token."""
    return {"Authorization": f"Bearer {TEST_API_KEY}"}


@pytest.fixture()
def mock_db_session():
    """A mock async DB session for endpoints that need one."""
    session = AsyncMock()
    return session


@pytest.fixture()
async def client(mock_db_session) -> AsyncGenerator[AsyncClient, None]:
    """Async HTTP client wired to the FastAPI app with dependency overrides."""

    # Override the DB dependency so DB-dependent routes don't need a real connection.
    app.dependency_overrides[get_db] = lambda: mock_db_session
    # Override auth so all requests are authenticated by default — individual
    # tests that verify auth behaviour can remove this override.
    app.dependency_overrides[verify_api_key] = lambda: TEST_API_KEY

    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as ac:
        yield ac

    app.dependency_overrides.clear()


@pytest.fixture()
async def unauthed_client() -> AsyncGenerator[AsyncClient, None]:
    """Async HTTP client with NO auth override — for testing 401/403 paths."""
    app.dependency_overrides.pop(verify_api_key, None)

    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as ac:
        yield ac

    app.dependency_overrides.clear()
