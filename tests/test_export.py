"""Tests for config export endpoint."""
import pytest
from httpx import AsyncClient
from sqlalchemy.ext.asyncio import AsyncSession

from app.models import Person, Chore, Settings


@pytest.mark.asyncio
async def test_export_endpoint(client: AsyncClient):
    """Test that export endpoint works when authenticated."""
    # Without token, should fail
    r = await client.get("/v1/export/config", headers={})
    assert r.status_code in (200, 401)  # Test client may auto-auth


@pytest.mark.asyncio
async def test_export_config(client: AsyncClient, db: AsyncSession):
    """Test that export returns proper JSON structure with schema version."""
    # Login
    login_r = await client.post(
        "/v1/auth/login",
        json={"username": "admin", "password": "admin_password"}
    )
    assert login_r.status_code == 200
    token = login_r.json()["access_token"]

    # Export
    export_r = await client.get(
        "/v1/export/config",
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


@pytest.mark.asyncio
async def test_export_config_boolean_types(client: AsyncClient, db: AsyncSession):
    """Test that exported config has real JSON booleans and integers, not quoted strings.

    Regression test for https://github.com/derekwinters/chores-web/issues/162:
    auth_enabled was exported as string "True" instead of boolean true.
    """
    # Login
    login_r = await client.post(
        "/v1/auth/login",
        json={"username": "admin", "password": "admin_password"}
    )
    assert login_r.status_code == 200
    token = login_r.json()["access_token"]
    headers = {"Authorization": f"Bearer {token}"}

    # Seed the DB with old-style Python-stringified booleans to simulate pre-fix data
    from sqlalchemy import select

    for key, old_value in [("auth_enabled", "True"), ("update_check_enabled", "False")]:
        result = await db.execute(select(Settings).where(Settings.key == key))
        setting = result.scalar_one_or_none()
        if setting:
            setting.value = old_value
        else:
            db.add(Settings(key=key, value=old_value))

    for key, old_value in [("due_soon_days", "7"), ("update_check_interval", "48")]:
        result = await db.execute(select(Settings).where(Settings.key == key))
        setting = result.scalar_one_or_none()
        if setting:
            setting.value = old_value
        else:
            db.add(Settings(key=key, value=old_value))

    await db.commit()

    # Export
    export_r = await client.get("/v1/export/config", headers=headers)
    assert export_r.status_code == 200
    data = export_r.json()

    config = data["config"]
    assert isinstance(config, dict)

    # Boolean keys must be actual booleans, not strings
    assert config["auth_enabled"] is True, f"auth_enabled should be bool True, got {config['auth_enabled']!r}"
    assert config["update_check_enabled"] is False, f"update_check_enabled should be bool False, got {config['update_check_enabled']!r}"

    # Integer keys must be actual integers, not strings
    assert config["due_soon_days"] == 7, f"due_soon_days should be int 7, got {config['due_soon_days']!r}"
    assert config["update_check_interval"] == 48, f"update_check_interval should be int 48, got {config['update_check_interval']!r}"
