"""Tests for password change endpoint."""
import pytest
from httpx import AsyncClient
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select

from app.models import Person
from app.security import hash_password, verify_password


@pytest.mark.asyncio
async def test_change_password_with_valid_old_password(client: AsyncClient, db: AsyncSession):
    """Test changing password with correct old password."""
    password = "old_password_123"
    new_password = "new_password_456"

    person = Person(
        name="PasswordChangeTest",
        username="pwdchange",
        password_hash=hash_password(password),
        is_admin=False
    )
    db.add(person)
    await db.commit()

    # Login to get token
    login_r = await client.post("/auth/login", json={"username": "pwdchange", "password": password})
    token = login_r.json()["access_token"]

    # Change password
    change_r = await client.put(
        "/auth/password",
        json={"old_password": password, "new_password": new_password},
        headers={"Authorization": f"Bearer {token}"}
    )
    assert change_r.status_code == 200

    # Verify can login with new password
    login_r2 = await client.post("/auth/login", json={"username": "pwdchange", "password": new_password})
    assert login_r2.status_code == 200

    # Verify cannot login with old password
    login_r3 = await client.post("/auth/login", json={"username": "pwdchange", "password": password})
    assert login_r3.status_code == 401


@pytest.mark.asyncio
async def test_change_password_with_invalid_old_password(client: AsyncClient, db: AsyncSession):
    """Test password change fails with incorrect old password."""
    password = "correct_password"

    person = Person(
        name="InvalidOldPwdTest",
        username="invalidoldpwd",
        password_hash=hash_password(password),
        is_admin=False
    )
    db.add(person)
    await db.commit()

    # Login to get token
    login_r = await client.post("/auth/login", json={"username": "invalidoldpwd", "password": password})
    token = login_r.json()["access_token"]

    # Try to change with wrong old password
    change_r = await client.put(
        "/auth/password",
        json={"old_password": "wrong_password", "new_password": "new_password_123"},
        headers={"Authorization": f"Bearer {token}"}
    )
    assert change_r.status_code == 401


@pytest.mark.asyncio
async def test_change_password_same_as_old(client: AsyncClient, db: AsyncSession):
    """Test password change fails if new password is same as old."""
    password = "same_password_123"

    person = Person(
        name="SamePwdTest",
        username="samepwd",
        password_hash=hash_password(password),
        is_admin=False
    )
    db.add(person)
    await db.commit()

    # Login to get token
    login_r = await client.post("/auth/login", json={"username": "samepwd", "password": password})
    token = login_r.json()["access_token"]

    # Try to change to same password
    change_r = await client.put(
        "/auth/password",
        json={"old_password": password, "new_password": password},
        headers={"Authorization": f"Bearer {token}"}
    )
    assert change_r.status_code == 400


@pytest.mark.asyncio
async def test_change_password_too_short(client: AsyncClient, db: AsyncSession):
    """Test password change fails if new password is too short."""
    password = "valid_password_123"

    person = Person(
        name="ShortPwdTest",
        username="shortpwd",
        password_hash=hash_password(password),
        is_admin=False
    )
    db.add(person)
    await db.commit()

    # Login to get token
    login_r = await client.post("/auth/login", json={"username": "shortpwd", "password": password})
    token = login_r.json()["access_token"]

    # Try to change to short password
    change_r = await client.put(
        "/auth/password",
        json={"old_password": password, "new_password": "short"},
        headers={"Authorization": f"Bearer {token}"}
    )
    assert change_r.status_code == 400


@pytest.mark.asyncio
async def test_change_password_without_token(client: AsyncClient):
    """Test password change without authorization header."""
    change_r = await client.put(
        "/auth/password",
        json={"old_password": "password", "new_password": "new_password"}
    )
    assert change_r.status_code == 401


@pytest.mark.asyncio
async def test_change_password_with_invalid_token(client: AsyncClient):
    """Test password change with invalid token."""
    change_r = await client.put(
        "/auth/password",
        json={"old_password": "password", "new_password": "new_password"},
        headers={"Authorization": "Bearer invalid.token.here"}
    )
    assert change_r.status_code == 401
