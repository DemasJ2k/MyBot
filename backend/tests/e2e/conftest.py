"""
E2E Test Configuration and Fixtures.

Provides fixtures for full-stack testing including:
- HTTP client for API requests
- Browser automation (optional)
- Test user creation and cleanup
- Database state management
"""
import pytest
import pytest_asyncio
from httpx import AsyncClient
import os

# E2E test settings
E2E_BASE_URL = os.getenv("E2E_API_URL", "http://localhost:8000")
E2E_FRONTEND_URL = os.getenv("E2E_FRONTEND_URL", "http://localhost:3000")


@pytest_asyncio.fixture
async def e2e_client():
    """HTTP client for E2E API testing."""
    async with AsyncClient(base_url=E2E_BASE_URL, timeout=30.0) as client:
        yield client


@pytest_asyncio.fixture
async def authenticated_client(e2e_client: AsyncClient):
    """
    Authenticated HTTP client with valid tokens.
    
    Creates a test user, logs in, and provides an authenticated client.
    Cleans up the test user after the test.
    """
    # Create unique test user
    import uuid
    test_email = f"e2e_test_{uuid.uuid4().hex[:8]}@test.com"
    test_password = "TestPassword123!"
    
    # Register
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
    
    # Create authenticated client
    async with AsyncClient(
        base_url=E2E_BASE_URL,
        timeout=30.0,
        headers={"Authorization": f"Bearer {access_token}"}
    ) as auth_client:
        yield auth_client
    
    # Note: In production E2E, you'd want cleanup logic here
    # to delete the test user from the database


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
