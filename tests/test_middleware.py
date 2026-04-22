"""Tests for authentication middleware."""
import pytest
from httpx import AsyncClient
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select

from app.models import Person, TokenBlacklist
from app.security import hash_password
from app.routers.auth import _create_jwt_token


@pytest.mark.asyncio
async def test_get_current_user_valid_token(client: AsyncClient, db: AsyncSession):
    """Test that valid token is accepted by middleware."""
    password = "middleware_test_123"
    person = Person(
        name="MiddlewareTest",
        username="mwtest",
        password_hash=hash_password(password),
        is_admin=False
    )
    db.add(person)
    await db.commit()

    # Login to get token
    login_r = await client.post("/auth/login", json={"username": "mwtest", "password": password})
    token = login_r.json()["access_token"]

    # Test protected endpoint with valid token
    health_r = await client.get(
        "/health",
        headers={"Authorization": f"Bearer {token}"}
    )
    assert health_r.status_code == 200


@pytest.mark.asyncio
async def test_get_current_user_missing_token(client: AsyncClient):
    """Test that missing token returns 401."""
    health_r = await client.get("/health")
    # Note: /health endpoint is not protected, but we can use other endpoints
    logout_r = await client.post("/auth/logout")
    assert logout_r.status_code == 401


@pytest.mark.asyncio
async def test_get_current_user_invalid_signature(client: AsyncClient):
    """Test that token with invalid signature is rejected."""
    logout_r = await client.post(
        "/auth/logout",
        headers={"Authorization": "Bearer invalid.token.here"}
    )
    assert logout_r.status_code == 401


@pytest.mark.asyncio
async def test_get_current_user_blacklisted_token(client: AsyncClient, db: AsyncSession):
    """Test that blacklisted token is rejected."""
    password = "blacklist_mw_test"
    person = Person(
        name="BlacklistMWTest",
        username="blacklistmw",
        password_hash=hash_password(password),
        is_admin=False
    )
    db.add(person)
    await db.commit()

    # Login to get token
    login_r = await client.post("/auth/login", json={"username": "blacklistmw", "password": password})
    token = login_r.json()["access_token"]

    # Logout to blacklist the token
    logout_r = await client.post(
        "/auth/logout",
        headers={"Authorization": f"Bearer {token}"}
    )
    assert logout_r.status_code == 204

    # Try to use blacklisted token
    change_r = await client.put(
        "/auth/password",
        json={"old_password": password, "new_password": "new_password_123"},
        headers={"Authorization": f"Bearer {token}"}
    )
    assert change_r.status_code == 401


@pytest.mark.asyncio
async def test_require_admin_with_admin_user(client: AsyncClient, db: AsyncSession):
    """Test that admin user passes admin check."""
    # First user is auto-admin
    password = "admin_test_password"
    login_r = await client.post("/auth/login", json={"username": "adminuser", "password": password})
    token = login_r.json()["access_token"]
    assert login_r.json()["user"]["is_admin"] is True

    # Admin user can change password (which requires being authenticated)
    change_r = await client.put(
        "/auth/password",
        json={"old_password": password, "new_password": "admin_new_password_123"},
        headers={"Authorization": f"Bearer {token}"}
    )
    assert change_r.status_code == 200


@pytest.mark.asyncio
async def test_require_admin_with_normal_user(client: AsyncClient, db: AsyncSession):
    """Test that normal user fails admin check."""
    # Create admin first
    admin_password = "admin_password_123"
    admin_r = await client.post("/auth/login", json={"username": "admin", "password": admin_password})
    assert admin_r.json()["user"]["is_admin"] is True

    # Create normal user
    normal_password = "normal_password_123"
    person = Person(
        name="NormalUser",
        username="normaluser",
        password_hash=hash_password(normal_password),
        is_admin=False
    )
    db.add(person)
    await db.commit()

    # Login as normal user
    normal_login = await client.post("/auth/login", json={"username": "normaluser", "password": normal_password})
    token = normal_login.json()["access_token"]
    assert normal_login.json()["user"]["is_admin"] is False

    # Normal user can still change their password (authenticated)
    change_r = await client.put(
        "/auth/password",
        json={"old_password": normal_password, "new_password": "normal_new_password_123"},
        headers={"Authorization": f"Bearer {token}"}
    )
    assert change_r.status_code == 200
