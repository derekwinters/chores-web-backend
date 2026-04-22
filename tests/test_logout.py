"""Tests for logout endpoint."""
import pytest
from httpx import AsyncClient
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select

from app.models import Person, TokenBlacklist
from app.security import hash_password
from app.routers.auth import _create_jwt_token


@pytest.mark.asyncio
async def test_logout_invalidates_token(client: AsyncClient, db: AsyncSession):
    """Test that logout adds token to blacklist."""
    # Create user
    password = "logout_test_password"
    person = Person(
        name="LogoutTest",
        username="logouttest",
        password_hash=hash_password(password),
        is_admin=False
    )
    db.add(person)
    await db.commit()

    # Login to get token
    login_r = await client.post("/auth/login", json={"username": "logouttest", "password": password})
    token = login_r.json()["access_token"]

    # Logout
    logout_r = await client.post(
        "/auth/logout",
        headers={"Authorization": f"Bearer {token}"}
    )
    assert logout_r.status_code == 204


@pytest.mark.asyncio
async def test_logout_without_token(client: AsyncClient):
    """Test logout without authorization header."""
    logout_r = await client.post("/auth/logout")
    assert logout_r.status_code == 401


@pytest.mark.asyncio
async def test_logout_with_invalid_token(client: AsyncClient):
    """Test logout with invalid token."""
    logout_r = await client.post(
        "/auth/logout",
        headers={"Authorization": "Bearer invalid.token.here"}
    )
    assert logout_r.status_code == 401


@pytest.mark.asyncio
async def test_token_added_to_blacklist(client: AsyncClient, db: AsyncSession):
    """Test that token is actually added to blacklist table."""
    # Create user
    password = "blacklist_test"
    person = Person(
        name="BlacklistTest",
        username="blacklisttest",
        password_hash=hash_password(password),
        is_admin=False
    )
    db.add(person)
    await db.commit()

    # Login
    login_r = await client.post("/auth/login", json={"username": "blacklisttest", "password": password})
    token = login_r.json()["access_token"]

    # Verify token is not in blacklist yet
    result = await db.execute(select(TokenBlacklist))
    initial_count = len(result.scalars().all())

    # Logout
    logout_r = await client.post(
        "/auth/logout",
        headers={"Authorization": f"Bearer {token}"}
    )
    assert logout_r.status_code == 204

    # Verify token was added to blacklist
    result = await db.execute(select(TokenBlacklist))
    final_count = len(result.scalars().all())
    assert final_count == initial_count + 1
