"""Tests for setup status endpoint."""
import pytest
from httpx import AsyncClient
from sqlalchemy.ext.asyncio import AsyncSession

from app.models import Person
from app.security import hash_password


@pytest.mark.asyncio
async def test_setup_status_needs_setup_when_no_users(client: AsyncClient):
    """Test that setup_needed is true when no users exist."""
    result = await client.get("/auth/setup-status")
    assert result.status_code == 200
    assert result.json()["setup_needed"] is True


@pytest.mark.asyncio
async def test_setup_status_setup_not_needed_after_user_created(client: AsyncClient, db: AsyncSession):
    """Test that setup_needed is false after first user created."""
    # Create first user
    admin = Person(
        name="Admin",
        username="admin",
        password_hash=hash_password("password123"),
        is_admin=True
    )
    db.add(admin)
    await db.commit()

    # Check status
    result = await client.get("/auth/setup-status")
    assert result.status_code == 200
    assert result.json()["setup_needed"] is False


@pytest.mark.asyncio
async def test_setup_status_no_auth_required(client: AsyncClient):
    """Test that setup status endpoint does not require authentication."""
    # Should work without any Authorization header
    result = await client.get("/auth/setup-status")
    assert result.status_code == 200
    assert "setup_needed" in result.json()
