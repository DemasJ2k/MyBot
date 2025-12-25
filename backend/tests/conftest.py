import pytest
import pytest_asyncio
from unittest.mock import AsyncMock, patch
from sqlalchemy.ext.asyncio import create_async_engine, AsyncSession, async_sessionmaker
from httpx import AsyncClient, ASGITransport
from app.main import app
from app.database import get_db
from app.models.base import Base
from app.models.user import User
from app.auth.password import hash_password
from app.core.rate_limiter import limiter


def pytest_configure(config):
    """Configure custom pytest markers."""
    config.addinivalue_line(
        "markers", "e2e: mark test as end-to-end (requires running services)"
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

