"""Tests for login endpoint."""
import pytest
from httpx import AsyncClient
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select
import json

from app.models import Person
from app.security import hash_password


@pytest.mark.asyncio
async def test_login_with_valid_credentials(client: AsyncClient, db: AsyncSession):
    """Test login with valid username and password."""
    # Create a test user
    password = "test_password_123"
    person = Person(
        name="TestUser",
        username="testuser",
        password_hash=hash_password(password),
        is_admin=False
    )
    db.add(person)
    await db.commit()

    # Login with correct credentials
    r = await client.post("/auth/login", json={"username": "testuser", "password": password})
    assert r.status_code == 200
    data = r.json()
    assert "access_token" in data
    assert data["token_type"] == "bearer"
    assert "user" in data
    assert data["user"]["username"] == "testuser"
    assert data["user"]["is_admin"] is False


@pytest.mark.asyncio
async def test_login_admin_flag(client: AsyncClient, db: AsyncSession):
    """Test that admin flag is included in login response."""
    password = "admin_password_123"
    admin_user = Person(
        name="AdminUser",
        username="admin",
        password_hash=hash_password(password),
        is_admin=True
    )
    db.add(admin_user)
    await db.commit()

    r = await client.post("/auth/login", json={"username": "admin", "password": password})
    assert r.status_code == 200
    data = r.json()
    assert data["user"]["is_admin"] is True


@pytest.mark.asyncio
async def test_login_invalid_username(client: AsyncClient, db: AsyncSession):
    """Test login with non-existent username (when users exist)."""
    # Create a user first to prevent auto-creation
    password = "existing_user_password"
    person = Person(
        name="ExistingUser",
        username="existing",
        password_hash=hash_password(password),
        is_admin=False
    )
    db.add(person)
    await db.commit()

    # Try to login with non-existent username
    r = await client.post("/auth/login", json={"username": "nonexistent", "password": "password123"})
    assert r.status_code == 401
    assert "detail" in r.json()


@pytest.mark.asyncio
async def test_login_invalid_password(client: AsyncClient, db: AsyncSession):
    """Test login with wrong password."""
    password = "correct_password"
    person = Person(
        name="TestUser2",
        username="testuser2",
        password_hash=hash_password(password),
        is_admin=False
    )
    db.add(person)
    await db.commit()

    r = await client.post("/auth/login", json={"username": "testuser2", "password": "wrong_password"})
    assert r.status_code == 401


@pytest.mark.asyncio
async def test_login_token_format(client: AsyncClient, db: AsyncSession):
    """Test that returned JWT token has valid format."""
    password = "token_test_123"
    person = Person(
        name="TokenTest",
        username="tokentest",
        password_hash=hash_password(password),
        is_admin=False
    )
    db.add(person)
    await db.commit()

    r = await client.post("/auth/login", json={"username": "tokentest", "password": password})
    data = r.json()
    token = data["access_token"]

    # JWT tokens have 3 parts separated by dots
    parts = token.split(".")
    assert len(parts) == 3, "JWT should have 3 parts"


@pytest.mark.asyncio
async def test_first_user_auto_admin(client: AsyncClient):
    """Test that first user in empty system becomes admin."""
    # Assuming database is empty (from test setup)
    password = "first_user_password"
    r = await client.post("/auth/login", json={"username": "firstuser", "password": password})

    # First login auto-creates user as admin
    assert r.status_code == 200
    data = r.json()
    assert data["user"]["is_admin"] is True
    assert data["user"]["username"] == "firstuser"


@pytest.mark.asyncio
async def test_second_user_not_admin(client: AsyncClient, db: AsyncSession):
    """Test that second user created manually is not admin."""
    password1 = "first_password"
    password2 = "second_password"

    # Create first user via login (will be admin)
    r1 = await client.post("/auth/login", json={"username": "user1", "password": password1})
    assert r1.status_code == 200
    assert r1.json()["user"]["is_admin"] is True

    # Create second user directly in database (not via login auto-create)
    person2 = Person(
        name="User2",
        username="user2",
        password_hash=hash_password(password2),
        is_admin=False
    )
    db.add(person2)
    await db.commit()

    # Login as second user (should not be admin)
    r2 = await client.post("/auth/login", json={"username": "user2", "password": password2})
    assert r2.status_code == 200
    assert r2.json()["user"]["is_admin"] is False
