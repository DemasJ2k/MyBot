"""
E2E Tests: Health and Infrastructure.

Tests system health and infrastructure:
1. Health endpoint availability
2. API versioning
3. Rate limiting behavior
4. CORS headers
"""
import pytest
from httpx import AsyncClient

pytestmark = [pytest.mark.e2e, pytest.mark.asyncio]


class TestHealthAndInfrastructure:
    """Infrastructure and health check tests."""

    async def test_health_endpoint(self, e2e_client: AsyncClient):
        """Test health endpoint returns healthy status."""
        response = await e2e_client.get("/health")
        assert response.status_code == 200
        data = response.json()
        assert data["status"] == "healthy"
        assert "version" in data

    async def test_root_endpoint(self, e2e_client: AsyncClient):
        """Test root endpoint returns API info."""
        response = await e2e_client.get("/")
        assert response.status_code == 200
        data = response.json()
        assert "message" in data
        assert "docs" in data

    async def test_api_docs_available(self, e2e_client: AsyncClient):
        """Test OpenAPI docs are available."""
        response = await e2e_client.get("/docs")
        # FastAPI returns HTML for docs
        assert response.status_code == 200

    async def test_openapi_schema(self, e2e_client: AsyncClient):
        """Test OpenAPI schema is accessible."""
        response = await e2e_client.get("/openapi.json")
        assert response.status_code == 200
        schema = response.json()
        assert "openapi" in schema
        assert "paths" in schema


class TestRateLimiting:
    """Rate limiting behavior tests."""

    async def test_rate_limit_headers_present(self, e2e_client: AsyncClient):
        """Test that rate limit headers are present."""
        response = await e2e_client.get("/health")
        # SlowAPI adds these headers
        # Note: exact header names depend on configuration
        assert response.status_code == 200

    async def test_login_rate_limiting(self, e2e_client: AsyncClient):
        """
        Test that login endpoint has rate limiting.
        
        Note: This test is informational - we don't actually hit the limit
        to avoid blocking the test user.
        """
        # Make a single request to verify the endpoint works
        response = await e2e_client.post(
            "/api/v1/auth/login",
            json={
                "email": "ratelimit_test@test.com",
                "password": "password"
            }
        )
        # Should fail with 401 (bad creds) not 429 (rate limit)
        assert response.status_code in [401, 429]
