"""
E2E Test Configuration and Fixtures.

Provides fixtures for full-stack testing including:
- HTTP client for API requests (ASGI transport or real server)
- Browser automation (optional)
- Test user creation and cleanup
- Database state management

When E2E_API_URL is set, tests will use real HTTP requests.
Otherwise, tests use ASGI transport with in-memory database (standalone mode).
"""
import pytest
import pytest_asyncio
from httpx import AsyncClient, ASGITransport
from unittest.mock import AsyncMock, patch
from sqlalchemy.ext.asyncio import create_async_engine, AsyncSession, async_sessionmaker
import os
import uuid

from app.main import app
from app.database import get_db
from app.models.base import Base
from app.models.user import User
from app.auth.password import hash_password
from app.core.rate_limiter import limiter

# E2E test settings
# If E2E_API_URL is not set, we'll use ASGI transport (standalone mode)
E2E_API_URL = os.getenv("E2E_API_URL")  # None means standalone
E2E_FRONTEND_URL = os.getenv("E2E_FRONTEND_URL", "http://localhost:3000")
USE_REAL_SERVER = E2E_API_URL is not None


@pytest_asyncio.fixture
async def e2e_db():
    """Create an isolated in-memory database for E2E tests in standalone mode."""
    if USE_REAL_SERVER:
        yield None
        return
    
    engine = create_async_engine("sqlite+aiosqlite:///:memory:")
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)
    maker = async_sessionmaker(engine, class_=AsyncSession, expire_on_commit=False)
    async with maker() as session:
        yield session
    await engine.dispose()


@pytest_asyncio.fixture
async def e2e_client(e2e_db):
    """HTTP client for E2E API testing.
    
    Uses real HTTP when E2E_API_URL is set, otherwise uses ASGI transport.
    """
    if USE_REAL_SERVER:
        async with AsyncClient(base_url=E2E_API_URL, timeout=30.0) as client:
            yield client
    else:
        # Use ASGI transport for standalone testing
        async def override_get_db():
            yield e2e_db

        app.dependency_overrides[get_db] = override_get_db
        limiter.reset()
        
        with patch('app.auth.blacklist.redis_client') as mock_redis:
            mock_redis.get = AsyncMock(return_value=None)
            mock_redis.setex = AsyncMock(return_value=True)
            
            transport = ASGITransport(app=app)
            async with AsyncClient(transport=transport, base_url="http://test") as client:
                yield client
        app.dependency_overrides.clear()


@pytest_asyncio.fixture
async def authenticated_client(e2e_client: AsyncClient, e2e_db):
    """
    Authenticated HTTP client with valid tokens.
    
    In standalone mode: Creates a test user directly in DB, then gets token.
    In real server mode: Registers user via API, then logs in.
    """
    test_email = f"e2e_test_{uuid.uuid4().hex[:8]}@test.com"
    test_password = "TestPassword123!"
    
    if USE_REAL_SERVER:
        # Real server mode: Register via API
        register_response = await e2e_client.post(
            "/api/v1/auth/register",
            json={
                "email": test_email,
                "password": test_password,
                "full_name": "E2E Test User"
            }
        )
        
        if register_response.status_code != 201:
            pytest.skip(f"Could not create test user: {register_response.text}")
        
        # Login
        login_response = await e2e_client.post(
            "/api/v1/auth/login",
            json={
                "email": test_email,
                "password": test_password
            }
        )
        
        if login_response.status_code != 200:
            pytest.skip(f"Could not login test user: {login_response.text}")
        
        tokens = login_response.json()
        access_token = tokens["access_token"]
        
        async with AsyncClient(
            base_url=E2E_API_URL,
            timeout=30.0,
            headers={"Authorization": f"Bearer {access_token}"}
        ) as auth_client:
            yield auth_client
    else:
        # Standalone mode: Create user directly in DB
        user = User(
            email=test_email,
            full_name="E2E Test User",
            hashed_password=hash_password(test_password),
            is_active=True
        )
        e2e_db.add(user)
        await e2e_db.commit()
        await e2e_db.refresh(user)
        
        # Login to get token via ASGI transport
        login_response = await e2e_client.post(
            "/api/v1/auth/login",
            json={"email": test_email, "password": test_password}
        )
        
        if login_response.status_code != 200:
            pytest.skip(f"Could not login test user: {login_response.text}")
        
        tokens = login_response.json()
        access_token = tokens["access_token"]
        
        # Create authenticated client using same ASGI transport
        async def override_get_db():
            yield e2e_db

        app.dependency_overrides[get_db] = override_get_db
        limiter.reset()
        
        with patch('app.auth.blacklist.redis_client') as mock_redis:
            mock_redis.get = AsyncMock(return_value=None)
            mock_redis.setex = AsyncMock(return_value=True)
            
            transport = ASGITransport(app=app)
            async with AsyncClient(
                transport=transport, 
                base_url="http://test",
                headers={"Authorization": f"Bearer {access_token}"}
            ) as auth_client:
                yield auth_client
        app.dependency_overrides.clear()


@pytest.fixture
def test_symbol():
    """Standard test symbol for market data tests."""
    return "AAPL"


@pytest.fixture
def test_strategy_config():
    """Standard test strategy configuration."""
    return {
        "name": "e2e_test_strategy",
        "type": "sma_crossover",
        "params": {
            "short_period": 10,
            "long_period": 20
        }
    }
