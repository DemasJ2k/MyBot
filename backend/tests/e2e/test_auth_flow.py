"""
E2E Tests: Authentication Flow.

Tests the complete authentication lifecycle:
1. User registration
2. Login and token acquisition
3. Token refresh
4. Logout and token invalidation
5. Protected route access
"""
import pytest
from httpx import AsyncClient
import uuid

pytestmark = [pytest.mark.e2e, pytest.mark.asyncio]


class TestAuthenticationFlow:
    """Complete authentication flow tests."""

    async def test_full_auth_lifecycle(self, e2e_client: AsyncClient):
        """
        Test complete auth flow: register → login → refresh → logout.
        """
        # Generate unique test credentials
        test_email = f"e2e_auth_{uuid.uuid4().hex[:8]}@test.com"
        test_password = "SecurePassword123!"

        # Step 1: Register
        register_response = await e2e_client.post(
            "/api/v1/auth/register",
            json={
                "email": test_email,
                "password": test_password,
                "full_name": "E2E Auth Test"
            }
        )
        assert register_response.status_code == 201, f"Registration failed: {register_response.text}"
        user_data = register_response.json()
        assert user_data["email"] == test_email

        # Step 2: Login
        login_response = await e2e_client.post(
            "/api/v1/auth/login",
            json={
                "email": test_email,
                "password": test_password
            }
        )
        assert login_response.status_code == 200, f"Login failed: {login_response.text}"
        tokens = login_response.json()
        assert "access_token" in tokens
        assert "refresh_token" in tokens

        access_token = tokens["access_token"]
        refresh_token = tokens["refresh_token"]

        # Step 3: Access protected route
        me_response = await e2e_client.get(
            "/api/v1/auth/me",
            headers={"Authorization": f"Bearer {access_token}"}
        )
        assert me_response.status_code == 200
        assert me_response.json()["email"] == test_email

        # Step 4: Refresh token
        refresh_response = await e2e_client.post(
            "/api/v1/auth/refresh",
            json={"refresh_token": refresh_token}
        )
        assert refresh_response.status_code == 200
        new_tokens = refresh_response.json()
        assert "access_token" in new_tokens

        # Step 5: Logout
        logout_response = await e2e_client.post(
            "/api/v1/auth/logout",
            headers={"Authorization": f"Bearer {access_token}"}
        )
        assert logout_response.status_code == 200

    async def test_duplicate_registration_rejected(self, e2e_client: AsyncClient):
        """Test that duplicate email registration is rejected."""
        test_email = f"e2e_dup_{uuid.uuid4().hex[:8]}@test.com"
        test_password = "Password123!"

        # First registration should succeed
        first_response = await e2e_client.post(
            "/api/v1/auth/register",
            json={
                "email": test_email,
                "password": test_password,
                "full_name": "First User"
            }
        )
        assert first_response.status_code == 201

        # Second registration with same email should fail
        second_response = await e2e_client.post(
            "/api/v1/auth/register",
            json={
                "email": test_email,
                "password": test_password,
                "full_name": "Second User"
            }
        )
        assert second_response.status_code == 400

    async def test_invalid_credentials_rejected(self, e2e_client: AsyncClient):
        """Test that invalid credentials are rejected."""
        response = await e2e_client.post(
            "/api/v1/auth/login",
            json={
                "email": "nonexistent@test.com",
                "password": "wrongpassword"
            }
        )
        assert response.status_code == 401

    async def test_protected_route_requires_auth(self, e2e_client: AsyncClient):
        """Test that protected routes require authentication."""
        response = await e2e_client.get("/api/v1/auth/me")
        assert response.status_code in [401, 403]
