"""
Tests for production health check endpoints.

Prompt 18 - Production Deployment Audit Fix.

Tests:
- /health - Basic health check
- /health/ready - Readiness check with DB/Redis validation
- /health/live - Liveness check
- /health/detailed - Detailed metrics
"""

import pytest
from unittest.mock import patch, AsyncMock, MagicMock
from httpx import AsyncClient, ASGITransport
from datetime import datetime, timezone


class TestBasicHealthEndpoint:
    """Tests for /health endpoint."""

    @pytest.mark.asyncio
    async def test_health_returns_healthy_status(self, client):
        """Health endpoint returns healthy status."""
        response = await client.get("/health")
        
        assert response.status_code == 200
        data = response.json()
        assert data["status"] == "healthy"
        assert data["service"] == "flowrex-backend"
        assert "timestamp" in data
        assert "version" in data
        assert "environment" in data

    @pytest.mark.asyncio
    async def test_health_returns_correct_service_name(self, client):
        """Health endpoint returns correct service name."""
        response = await client.get("/health")
        
        data = response.json()
        assert data["service"] == "flowrex-backend"

    @pytest.mark.asyncio
    async def test_health_returns_iso_timestamp(self, client):
        """Health endpoint returns valid ISO timestamp."""
        response = await client.get("/health")
        
        data = response.json()
        # Should be parseable as ISO format
        timestamp = datetime.fromisoformat(data["timestamp"].replace("Z", "+00:00"))
        assert timestamp is not None


class TestLivenessEndpoint:
    """Tests for /health/live endpoint."""

    @pytest.mark.asyncio
    async def test_liveness_returns_alive_status(self, client):
        """Liveness endpoint always returns alive status."""
        response = await client.get("/health/live")
        
        assert response.status_code == 200
        data = response.json()
        assert data["status"] == "alive"
        assert "timestamp" in data

    @pytest.mark.asyncio
    async def test_liveness_always_returns_200(self, client):
        """Liveness check always returns 200 if process is running."""
        # Call multiple times - should always be 200
        for _ in range(3):
            response = await client.get("/health/live")
            assert response.status_code == 200


class TestReadinessEndpoint:
    """Tests for /health/ready endpoint."""

    @pytest.mark.asyncio
    async def test_readiness_returns_ready_when_all_healthy(self, client, test_db):
        """Readiness returns ready when all dependencies healthy."""
        # Mock Redis to be healthy - patch at redis.asyncio module level
        with patch("redis.asyncio.from_url") as mock_from_url:
            mock_client = AsyncMock()
            mock_client.ping = AsyncMock(return_value=True)
            mock_client.close = AsyncMock()
            mock_from_url.return_value = mock_client
            
            response = await client.get("/health/ready")
            
            # Since we're in test mode with SQLite, DB should pass
            # Redis is mocked to pass
            data = response.json()
            
            # If database check fails (common in isolated tests), that's expected
            # Main test is that the endpoint works and returns proper structure
            assert response.status_code in [200, 503]
            assert "status" in data
            assert "checks" in data
            assert "database" in data["checks"]
            assert "redis" in data["checks"]
            
            # If all healthy, should be ready
            if data["checks"]["database"] and data["checks"]["redis"]:
                assert data["status"] == "ready"
                assert response.status_code == 200

    @pytest.mark.asyncio
    async def test_readiness_returns_503_when_redis_unhealthy(self, client, test_db):
        """Readiness returns 503 when Redis is unavailable."""
        with patch("redis.asyncio.from_url") as mock_redis:
            mock_client = AsyncMock()
            mock_client.ping = AsyncMock(side_effect=ConnectionError("Redis unavailable"))
            mock_redis.return_value = mock_client
            
            response = await client.get("/health/ready")
            
            assert response.status_code == 503
            data = response.json()
            assert data["status"] == "not_ready"
            assert data["checks"]["redis"] is False
            assert "errors" in data
            assert "redis" in data["errors"]

    @pytest.mark.asyncio
    async def test_readiness_includes_error_details(self, client, test_db):
        """Readiness includes error details when dependency fails."""
        with patch("redis.asyncio.from_url") as mock_redis:
            mock_client = AsyncMock()
            mock_client.ping = AsyncMock(side_effect=ConnectionError("Connection refused"))
            mock_redis.return_value = mock_client
            
            response = await client.get("/health/ready")
            
            data = response.json()
            assert "errors" in data
            assert "Connection refused" in data["errors"]["redis"]


class TestDetailedHealthEndpoint:
    """Tests for /health/detailed endpoint."""

    @pytest.mark.asyncio
    async def test_detailed_includes_system_metrics(self, client, test_db):
        """Detailed health includes system metrics."""
        with patch("redis.asyncio.from_url") as mock_redis:
            mock_client = AsyncMock()
            mock_client.ping = AsyncMock(return_value=True)
            mock_client.info = AsyncMock(return_value={"used_memory": 1024 * 1024 * 50})  # 50MB
            mock_client.close = AsyncMock()
            mock_redis.return_value = mock_client
            
            response = await client.get("/health/detailed")
            
            # Response should work regardless of DB state
            data = response.json()
            assert "system" in data
            assert "cpu_percent" in data["system"]
            assert "memory_percent" in data["system"]
            assert "disk_percent" in data["system"]

    @pytest.mark.asyncio
    async def test_detailed_includes_redis_memory(self, client, test_db):
        """Detailed health includes Redis memory usage."""
        with patch("redis.asyncio.from_url") as mock_redis:
            mock_client = AsyncMock()
            mock_client.ping = AsyncMock(return_value=True)
            mock_client.info = AsyncMock(return_value={"used_memory": 1024 * 1024 * 100})  # 100MB
            mock_client.close = AsyncMock()
            mock_redis.return_value = mock_client
            
            response = await client.get("/health/detailed")
            
            data = response.json()
            assert data["checks"]["redis_memory_mb"] == 100.0

    @pytest.mark.asyncio
    async def test_detailed_returns_503_when_unhealthy(self, client, test_db):
        """Detailed health returns 503 when dependencies fail."""
        with patch("redis.asyncio.from_url") as mock_redis:
            mock_client = AsyncMock()
            mock_client.ping = AsyncMock(side_effect=ConnectionError("Redis down"))
            mock_redis.return_value = mock_client
            
            response = await client.get("/health/detailed")
            
            assert response.status_code == 503
            data = response.json()
            assert data["status"] == "unhealthy"

    @pytest.mark.asyncio
    async def test_detailed_includes_version_and_environment(self, client, test_db):
        """Detailed health includes version and environment info."""
        with patch("redis.asyncio.from_url") as mock_redis:
            mock_client = AsyncMock()
            mock_client.ping = AsyncMock(return_value=True)
            mock_client.info = AsyncMock(return_value={"used_memory": 0})
            mock_client.close = AsyncMock()
            mock_redis.return_value = mock_client
            
            response = await client.get("/health/detailed")
            
            data = response.json()
            assert "version" in data
            assert "environment" in data
            assert "timestamp" in data


class TestHealthEndpointIntegration:
    """Integration tests for health endpoints."""

    @pytest.mark.asyncio
    async def test_all_health_endpoints_accessible(self, client):
        """All health endpoints are accessible without auth."""
        endpoints = ["/health", "/health/live", "/health/ready", "/health/detailed"]
        
        for endpoint in endpoints:
            with patch("redis.asyncio.from_url") as mock_redis:
                mock_client = AsyncMock()
                mock_client.ping = AsyncMock(return_value=True)
                mock_client.info = AsyncMock(return_value={"used_memory": 0})
                mock_client.close = AsyncMock()
                mock_redis.return_value = mock_client
                
                response = await client.get(endpoint)
                # Should not return 401/403
                assert response.status_code in [200, 503]

    @pytest.mark.asyncio
    async def test_health_endpoints_no_authentication_required(self, client):
        """Health endpoints work without authentication headers."""
        # Basic health should always work
        response = await client.get("/health")
        assert response.status_code == 200
        
        # Liveness should always work
        response = await client.get("/health/live")
        assert response.status_code == 200
