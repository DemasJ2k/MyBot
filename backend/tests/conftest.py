"""
Global pytest configuration and fixtures for Flowrex testing.

Test Pyramid:
- Unit tests (70%): Fast, isolated, no external dependencies
- Integration tests (20%): Database interactions, service layer
- E2E tests (10%): Full stack, critical user journeys
"""
import pytest
import pytest_asyncio
from unittest.mock import AsyncMock, patch, MagicMock
from sqlalchemy.ext.asyncio import create_async_engine, AsyncSession, async_sessionmaker
from sqlalchemy.pool import NullPool
from httpx import AsyncClient, ASGITransport
from datetime import datetime, timezone
from typing import AsyncGenerator, Generator

from app.main import app
from app.database import get_db
from app.models.base import Base
from app.models.user import User
from app.auth.password import hash_password
from app.core.rate_limiter import limiter


# Test database URL (in-memory SQLite for speed)
TEST_DATABASE_URL = "sqlite+aiosqlite:///:memory:"


def pytest_configure(config):
    """Configure custom pytest markers."""
    config.addinivalue_line(
        "markers", "e2e: mark test as end-to-end (requires running services)"
    )
    config.addinivalue_line(
        "markers", "unit: mark test as unit test (fast, no dependencies)"
    )
    config.addinivalue_line(
        "markers", "integration: mark test as integration test (database required)"
    )
    config.addinivalue_line(
        "markers", "slow: mark test as slow (> 1 second)"
    )
    config.addinivalue_line(
        "markers", "crosscheck: mark test as CROSSCHECK architectural validation"
    )


def pytest_collection_modifyitems(config, items):
    """Skip E2E tests unless explicitly requested."""
    if not config.getoption("--e2e", default=False):
        skip_e2e = pytest.mark.skip(reason="E2E tests require --e2e flag")
        for item in items:
            if "e2e" in item.keywords:
                item.add_marker(skip_e2e)


def pytest_addoption(parser):
    """Add custom command line options."""
    parser.addoption(
        "--e2e",
        action="store_true",
        default=False,
        help="Run end-to-end tests (requires running services)"
    )


@pytest_asyncio.fixture
async def test_db():
    """Create an isolated in-memory test database."""
    engine = create_async_engine("sqlite+aiosqlite:///:memory:")
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)
    maker = async_sessionmaker(engine, class_=AsyncSession, expire_on_commit=False)
    async with maker() as session:
        yield session
    await engine.dispose()


# Alias for tests using 'db' fixture name
@pytest_asyncio.fixture
async def db():
    """Alias for test_db - creates isolated in-memory test database."""
    engine = create_async_engine("sqlite+aiosqlite:///:memory:")
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)
    maker = async_sessionmaker(engine, class_=AsyncSession, expire_on_commit=False)
    async with maker() as session:
        yield session
    await engine.dispose()


@pytest_asyncio.fixture
async def test_user(test_db):
    """Create a test user for multi-tenancy tests."""
    user = User(
        email="test@example.com",
        full_name="Test User",
        hashed_password=hash_password("testpass123"),
        is_active=True
    )
    test_db.add(user)
    await test_db.commit()
    await test_db.refresh(user)
    return user


@pytest_asyncio.fixture
async def client(test_db):
    async def override_get_db():
        yield test_db

    app.dependency_overrides[get_db] = override_get_db
    
    # Reset rate limiter storage for test isolation
    limiter.reset()
    
    # Mock Redis blacklist check to avoid Redis dependency in tests
    with patch('app.auth.blacklist.redis_client') as mock_redis:
        mock_redis.get = AsyncMock(return_value=None)  # Token not blacklisted
        mock_redis.setex = AsyncMock(return_value=True)
        
        transport = ASGITransport(app=app)
        async with AsyncClient(transport=transport, base_url="http://test") as ac:
            yield ac
    app.dependency_overrides.clear()


@pytest_asyncio.fixture
async def authenticated_client(test_db, test_user):
    """Create a test client with authenticated user token."""
    async def override_get_db():
        yield test_db

    app.dependency_overrides[get_db] = override_get_db
    limiter.reset()
    
    with patch('app.auth.blacklist.redis_client') as mock_redis:
        mock_redis.get = AsyncMock(return_value=None)
        mock_redis.setex = AsyncMock(return_value=True)
        
        transport = ASGITransport(app=app)
        async with AsyncClient(transport=transport, base_url="http://test") as ac:
            # Login to get token
            response = await ac.post(
                "/api/v1/auth/login",
                data={"username": test_user.email, "password": "testpass123"}
            )
            if response.status_code == 200:
                token = response.json()["access_token"]
                ac.headers["Authorization"] = f"Bearer {token}"
            yield ac
    app.dependency_overrides.clear()


@pytest.fixture
def mock_twelvedata_client():
    """Mock TwelveData API client for testing."""
    mock_client = MagicMock()
    mock_client.get_time_series = AsyncMock(return_value={
        "values": [
            {
                "datetime": "2024-01-01 00:00:00",
                "open": "1.1000",
                "high": "1.1050",
                "low": "1.0950",
                "close": "1.1020",
                "volume": "10000",
            }
        ]
    })
    mock_client.get_quote = AsyncMock(return_value={
        "symbol": "EURUSD",
        "price": "1.1020",
        "bid": "1.1019",
        "ask": "1.1021",
    })
    return mock_client


@pytest.fixture
def sample_candle_data():
    """Provide sample candle data for strategy tests."""
    return [
        {
            "timestamp": datetime(2024, 1, 1, i, 0, 0, tzinfo=timezone.utc),
            "open": 1.1000 + i * 0.0001,
            "high": 1.1010 + i * 0.0001,
            "low": 1.0990 + i * 0.0001,
            "close": 1.1005 + i * 0.0001,
            "volume": 1000,
        }
        for i in range(50)
    ]


@pytest.fixture
def mock_broker():
    """Mock broker adapter for execution tests."""
    mock = MagicMock()
    mock.submit_order = AsyncMock(return_value={
        "order_id": "TEST-001",
        "status": "filled",
        "filled_price": 1.1020,
        "filled_quantity": 0.1,
    })
    mock.get_account_info = AsyncMock(return_value={
        "balance": 10000.0,
        "equity": 10050.0,
        "margin_used": 500.0,
    })
    mock.get_positions = AsyncMock(return_value=[])
    return mock

