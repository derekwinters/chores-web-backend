"""Tests for config endpoints."""
import pytest
from httpx import AsyncClient
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models import Settings


@pytest.mark.asyncio
async def test_get_config_default_values(authenticated_client: AsyncClient):
    """Test that config returns default values when no settings are stored."""
    r = await authenticated_client.get("/v1/config")
    assert r.status_code == 200
    data = r.json()
    assert data["title"] == "Family Chores"
    assert data["auth_enabled"] is True
    assert data["timezone"] == "UTC"
    assert data["due_soon_days"] == 3


@pytest.mark.asyncio
async def test_get_config_custom_values(authenticated_client: AsyncClient, db: AsyncSession):
    """Test that config returns custom values when settings are stored."""
    # Store custom settings - update existing ones from setup
    from sqlalchemy import select

    # Update title
    result = await db.execute(select(Settings).where(Settings.key == "title"))
    title_setting = result.scalar_one_or_none()
    if title_setting:
        title_setting.value = "My Chores"
    else:
        db.add(Settings(key="title", value="My Chores"))

    # Update auth_enabled
    result = await db.execute(select(Settings).where(Settings.key == "auth_enabled"))
    auth_setting = result.scalar_one_or_none()
    if auth_setting:
        auth_setting.value = "false"
    else:
        db.add(Settings(key="auth_enabled", value="false"))

    # Update timezone
    result = await db.execute(select(Settings).where(Settings.key == "timezone"))
    tz_setting = result.scalar_one_or_none()
    if tz_setting:
        tz_setting.value = "America/New_York"
    else:
        db.add(Settings(key="timezone", value="America/New_York"))

    # Add due_soon_days
    result = await db.execute(select(Settings).where(Settings.key == "due_soon_days"))
    due_setting = result.scalar_one_or_none()
    if due_setting:
        due_setting.value = "5"
    else:
        db.add(Settings(key="due_soon_days", value="5"))

    await db.commit()

    r = await authenticated_client.get("/v1/config")
    assert r.status_code == 200
    data = r.json()
    assert data["title"] == "My Chores"
    assert data["auth_enabled"] is False
    assert data["timezone"] == "America/New_York"
    assert data["due_soon_days"] == 5


@pytest.mark.asyncio
async def test_update_config_title(authenticated_client: AsyncClient):
    """Test updating the title."""
    r = await authenticated_client.put("/v1/config", json={"title": "Updated Title"})
    assert r.status_code == 200
    data = r.json()
    assert data["title"] == "Updated Title"

    # Verify persistence
    r = await authenticated_client.get("/v1/config")
    assert r.status_code == 200
    assert r.json()["title"] == "Updated Title"


@pytest.mark.asyncio
async def test_update_config_auth_enabled(authenticated_client: AsyncClient):
    """Test updating auth_enabled."""
    r = await authenticated_client.put("/v1/config", json={"auth_enabled": False})
    assert r.status_code == 200
    data = r.json()
    assert data["auth_enabled"] is False

    # Verify persistence
    r = await authenticated_client.get("/v1/config")
    assert r.status_code == 200
    assert r.json()["auth_enabled"] is False


@pytest.mark.asyncio
async def test_update_config_timezone(authenticated_client: AsyncClient):
    """Test updating timezone."""
    r = await authenticated_client.put("/v1/config", json={"timezone": "Europe/London"})
    assert r.status_code == 200
    data = r.json()
    assert data["timezone"] == "Europe/London"

    # Verify persistence
    r = await authenticated_client.get("/v1/config")
    assert r.status_code == 200
    assert r.json()["timezone"] == "Europe/London"


@pytest.mark.asyncio
async def test_update_config_due_soon_days(authenticated_client: AsyncClient):
    """Test updating due_soon_days."""
    r = await authenticated_client.put("/v1/config", json={"due_soon_days": 7})
    assert r.status_code == 200
    data = r.json()
    assert data["due_soon_days"] == 7

    # Verify persistence
    r = await authenticated_client.get("/v1/config")
    assert r.status_code == 200
    assert r.json()["due_soon_days"] == 7


@pytest.mark.asyncio
async def test_update_config_due_soon_days_invalid_low(authenticated_client: AsyncClient):
    """Test that due_soon_days below 1 is rejected."""
    r = await authenticated_client.put("/v1/config", json={"due_soon_days": 0})
    assert r.status_code == 422  # Validation error


@pytest.mark.asyncio
async def test_update_config_due_soon_days_invalid_high(authenticated_client: AsyncClient):
    """Test that due_soon_days above 365 is rejected."""
    r = await authenticated_client.put("/v1/config", json={"due_soon_days": 366})
    assert r.status_code == 422  # Validation error


@pytest.mark.asyncio
async def test_update_config_due_soon_days_boundary_low(authenticated_client: AsyncClient):
    """Test that due_soon_days of 1 is accepted."""
    r = await authenticated_client.put("/v1/config", json={"due_soon_days": 1})
    assert r.status_code == 200
    data = r.json()
    assert data["due_soon_days"] == 1


@pytest.mark.asyncio
async def test_update_config_due_soon_days_boundary_high(authenticated_client: AsyncClient):
    """Test that due_soon_days of 365 is accepted."""
    r = await authenticated_client.put("/v1/config", json={"due_soon_days": 365})
    assert r.status_code == 200
    data = r.json()
    assert data["due_soon_days"] == 365


@pytest.mark.asyncio
async def test_update_config_auth_enabled_stores_lowercase(authenticated_client: AsyncClient, db: AsyncSession):
    """Test that PUT /config with auth_enabled=false stores lowercase 'false' in the DB, not Python 'False'."""
    r = await authenticated_client.put("/v1/config", json={"auth_enabled": False})
    assert r.status_code == 200
    assert r.json()["auth_enabled"] is False

    result = await db.execute(select(Settings).where(Settings.key == "auth_enabled"))
    setting = result.scalar_one_or_none()
    assert setting is not None
    assert setting.value == "false", f"Expected 'false' but got '{setting.value}'"


@pytest.mark.asyncio
async def test_update_config_update_check_enabled_stores_lowercase(authenticated_client: AsyncClient, db: AsyncSession):
    """Test that PUT /config with update_check_enabled=false stores lowercase 'false' in the DB."""
    r = await authenticated_client.put("/v1/config", json={"update_check_enabled": False})
    assert r.status_code == 200
    assert r.json()["update_check_enabled"] is False

    result = await db.execute(select(Settings).where(Settings.key == "update_check_enabled"))
    setting = result.scalar_one_or_none()
    assert setting is not None
    assert setting.value == "false", f"Expected 'false' but got '{setting.value}'"


@pytest.mark.asyncio
async def test_update_config_multiple_fields(authenticated_client: AsyncClient):
    """Test updating multiple config fields at once."""
    r = await authenticated_client.put("/v1/config", json={
        "title": "New Title",
        "timezone": "Asia/Tokyo",
        "due_soon_days": 10
    })
    assert r.status_code == 200
    data = r.json()
    assert data["title"] == "New Title"
    assert data["timezone"] == "Asia/Tokyo"
    assert data["due_soon_days"] == 10

    # Verify persistence
    r = await authenticated_client.get("/v1/config")
    assert r.status_code == 200
    data = r.json()
    assert data["title"] == "New Title"
    assert data["timezone"] == "Asia/Tokyo"
    assert data["due_soon_days"] == 10


# ── due_time_hour tests ───────────────────────────────────────────────────────

@pytest.mark.asyncio
async def test_get_config_default_due_time_hour(authenticated_client: AsyncClient):
    """GET /config returns due_time_hour defaulting to 6."""
    r = await authenticated_client.get("/v1/config")
    assert r.status_code == 200
    assert r.json()["due_time_hour"] == 6


@pytest.mark.asyncio
async def test_get_config_custom_due_time_hour(authenticated_client: AsyncClient, db: AsyncSession):
    """GET /config returns stored due_time_hour when set."""
    db.add(Settings(key="due_time_hour", value="14"))
    await db.commit()

    r = await authenticated_client.get("/v1/config")
    assert r.status_code == 200
    assert r.json()["due_time_hour"] == 14


@pytest.mark.asyncio
async def test_update_config_due_time_hour(authenticated_client: AsyncClient):
    """PUT /config saves due_time_hour and returns it."""
    r = await authenticated_client.put("/v1/config", json={"due_time_hour": 8})
    assert r.status_code == 200
    assert r.json()["due_time_hour"] == 8

    # Verify persistence
    r = await authenticated_client.get("/v1/config")
    assert r.status_code == 200
    assert r.json()["due_time_hour"] == 8


@pytest.mark.asyncio
async def test_update_config_due_time_hour_boundary_low(authenticated_client: AsyncClient):
    """PUT /config accepts due_time_hour=0 (midnight)."""
    r = await authenticated_client.put("/v1/config", json={"due_time_hour": 0})
    assert r.status_code == 200
    assert r.json()["due_time_hour"] == 0


@pytest.mark.asyncio
async def test_update_config_due_time_hour_boundary_high(authenticated_client: AsyncClient):
    """PUT /config accepts due_time_hour=23 (11 PM)."""
    r = await authenticated_client.put("/v1/config", json={"due_time_hour": 23})
    assert r.status_code == 200
    assert r.json()["due_time_hour"] == 23


@pytest.mark.asyncio
async def test_update_config_due_time_hour_invalid_low(authenticated_client: AsyncClient):
    """PUT /config rejects due_time_hour below 0."""
    r = await authenticated_client.put("/v1/config", json={"due_time_hour": -1})
    assert r.status_code == 422


@pytest.mark.asyncio
async def test_update_config_due_time_hour_invalid_high(authenticated_client: AsyncClient):
    """PUT /config rejects due_time_hour above 23."""
    r = await authenticated_client.put("/v1/config", json={"due_time_hour": 24})
    assert r.status_code == 422


@pytest.mark.asyncio
async def test_update_config_due_time_hour_reschedules_transition(authenticated_client: AsyncClient):
    """PUT /config with due_time_hour reschedules the transition job."""
    from unittest.mock import patch
    with patch("app.routers.config.reschedule_transition") as mock_reschedule:
        r = await authenticated_client.put("/v1/config", json={"due_time_hour": 7})
        assert r.status_code == 200
        mock_reschedule.assert_called_once_with(7, "UTC")


@pytest.mark.asyncio
async def test_update_config_timezone_reschedules_transition(authenticated_client: AsyncClient):
    """PUT /config with timezone reschedules the transition job."""
    from unittest.mock import patch
    with patch("app.routers.config.reschedule_transition") as mock_reschedule:
        r = await authenticated_client.put("/v1/config", json={"timezone": "America/Chicago"})
        assert r.status_code == 200
        mock_reschedule.assert_called_once_with(6, "America/Chicago")


@pytest.mark.asyncio
async def test_update_config_title_does_not_reschedule(authenticated_client: AsyncClient):
    """PUT /config with only title does NOT reschedule the transition job."""
    from unittest.mock import patch
    with patch("app.routers.config.reschedule_transition") as mock_reschedule:
        r = await authenticated_client.put("/v1/config", json={"title": "New Title"})
        assert r.status_code == 200
        mock_reschedule.assert_not_called()
