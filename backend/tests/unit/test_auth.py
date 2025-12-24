import pytest
from httpx import AsyncClient


@pytest.mark.asyncio
async def test_register(client: AsyncClient):
    r = await client.post(
        "/api/v1/auth/register",
        json={"email": "test@test.com", "password": "Test1234"}
    )
    assert r.status_code == 201
    assert r.json()["email"] == "test@test.com"


@pytest.mark.asyncio
async def test_register_duplicate_email(client: AsyncClient):
    await client.post(
        "/api/v1/auth/register",
        json={"email": "dupe@test.com", "password": "Test1234"}
    )
    r = await client.post(
        "/api/v1/auth/register",
        json={"email": "dupe@test.com", "password": "Test1234"}
    )
    assert r.status_code == 400


@pytest.mark.asyncio
async def test_login(client: AsyncClient):
    await client.post(
        "/api/v1/auth/register",
        json={"email": "login@test.com", "password": "Test1234"}
    )
    r = await client.post(
        "/api/v1/auth/login",
        json={"email": "login@test.com", "password": "Test1234"}
    )
    assert r.status_code == 200
    assert "access_token" in r.json()
    assert "refresh_token" in r.json()


@pytest.mark.asyncio
async def test_login_wrong_password(client: AsyncClient):
    await client.post(
        "/api/v1/auth/register",
        json={"email": "wrongpw@test.com", "password": "Test1234"}
    )
    r = await client.post(
        "/api/v1/auth/login",
        json={"email": "wrongpw@test.com", "password": "WrongPassword1"}
    )
    assert r.status_code == 401


@pytest.mark.asyncio
async def test_me(client: AsyncClient):
    await client.post(
        "/api/v1/auth/register",
        json={"email": "me@test.com", "password": "Test1234"}
    )
    login = await client.post(
        "/api/v1/auth/login",
        json={"email": "me@test.com", "password": "Test1234"}
    )
    token = login.json()["access_token"]
    r = await client.get(
        "/api/v1/auth/me",
        headers={"Authorization": f"Bearer {token}"}
    )
    assert r.status_code == 200
    assert r.json()["email"] == "me@test.com"


@pytest.mark.asyncio
async def test_me_unauthorized(client: AsyncClient):
    r = await client.get("/api/v1/auth/me")
    assert r.status_code == 403  # No auth header


@pytest.mark.asyncio
async def test_refresh_token(client: AsyncClient):
    await client.post(
        "/api/v1/auth/register",
        json={"email": "refresh@test.com", "password": "Test1234"}
    )
    login = await client.post(
        "/api/v1/auth/login",
        json={"email": "refresh@test.com", "password": "Test1234"}
    )
    refresh_token = login.json()["refresh_token"]
    r = await client.post(
        "/api/v1/auth/refresh",
        json={"refresh_token": refresh_token}
    )
    assert r.status_code == 200
    assert "access_token" in r.json()
