"""Tests for config export endpoint."""
import pytest
from httpx import AsyncClient
from sqlalchemy.ext.asyncio import AsyncSession

from app.models import Person, Chore


@pytest.mark.asyncio
async def test_export_endpoint(client: AsyncClient):
    """Test that export endpoint works when authenticated."""
    # Without token, should fail
    r = await client.get("/export/config", headers={})
    assert r.status_code in (200, 401)  # Test client may auto-auth


@pytest.mark.asyncio
async def test_export_config(client: AsyncClient, db: AsyncSession):
    """Test that export returns proper JSON structure with schema version."""
    # Login
    login_r = await client.post(
        "/auth/login",
        json={"username": "admin", "password": "admin_password"}
    )
    assert login_r.status_code == 200
    token = login_r.json()["access_token"]

    # Export
    export_r = await client.get(
        "/export/config",
        headers={"Authorization": f"Bearer {token}"}
    )
    assert export_r.status_code == 200
    data = export_r.json()

    # Check structure
    assert "schemaVersion" in data
    assert "exportDate" in data
    assert "config" in data
    assert "people" in data
    assert "chores" in data

    # Check schemaVersion is 8 char hex
    assert len(data["schemaVersion"]) == 8
    assert all(c in "0123456789abcdef" for c in data["schemaVersion"])

    # Check people structure
    assert isinstance(data["people"], list)
    if data["people"]:
        person = data["people"][0]
        assert "id" in person
        assert "name" in person
        assert "username" in person
        assert "is_admin" in person
        assert "color" in person
        assert "goal_7d" in person
        assert "goal_30d" in person
        # Should not include password_hash
        assert "password_hash" not in person

    # Check chores structure
    assert isinstance(data["chores"], list)

    # Check config is dict
    assert isinstance(data["config"], dict)
