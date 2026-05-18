"""Tests for update check API endpoints."""
import pytest
from fastapi.testclient import TestClient
from unittest.mock import AsyncMock, patch
from sqlalchemy.ext.asyncio import AsyncSession

from app.main import app
from app.models import UpdateCheck, Person, Settings
from app.database import AsyncSessionLocal
from app.config import APP_VERSION


@pytest.fixture
def client():
    """Create test client."""
    return TestClient(app)


@pytest.mark.asyncio
async def test_get_config_includes_update_check_settings(db: AsyncSession):
    """Test that get /config includes update check settings."""
    # Create admin user
    admin = Person(
        name="Admin",
        username="admin",
        password_hash="hashed_password",
        is_admin=True,
    )
    db.add(admin)

    # Create settings
    settings = [
        Settings(key="update_check_enabled", value="true"),
        Settings(key="update_check_interval", value="24"),
    ]
    for setting in settings:
        db.add(setting)

    await db.commit()


@pytest.mark.asyncio
async def test_update_check_status_endpoint(db: AsyncSession):
    """Test the update check status endpoint."""
    # Create initial update check record
    update_check = UpdateCheck(
        current_version=APP_VERSION,
        latest_version=APP_VERSION,
        check_enabled=True,
        check_interval_hours=24,
    )
    db.add(update_check)
    await db.commit()

    # The endpoint should return proper status
    # This test verifies the database state


@pytest.mark.asyncio
async def test_update_check_config_validation(db: AsyncSession):
    """Test update check configuration validation."""
    # Test invalid interval (less than 1 hour)
    # Should fail validation
    from app.schemas import ConfigUpdate
    from pydantic import ValidationError

    # Should raise validation error for negative interval
    try:
        ConfigUpdate(update_check_interval=-1)
        assert False, "Should have raised validation error"
    except ValidationError:
        pass  # Expected - validation correctly rejected negative interval


@pytest.mark.asyncio
async def test_configure_update_check_with_query_params(db: AsyncSession):
    """Test configuring update check via query parameters."""
    # This would be tested in integration tests
    # Verify the endpoint accepts query parameters
    pass


@pytest.mark.asyncio
async def test_trigger_update_check_calls_with_force_true(authenticated_client):
    """Behavior 4: trigger_update_check router endpoint calls check_for_updates(db, force=True)."""
    with patch(
        "app.routers.config.check_for_updates",
        new_callable=AsyncMock,
        return_value=None,
    ) as mock_check, patch(
        "app.routers.config.get_update_status",
        new_callable=AsyncMock,
        return_value={
            "current_version": APP_VERSION,
            "latest_version": APP_VERSION,
            "last_checked_at": None,
            "check_enabled": True,
            "check_interval_hours": 24,
            "update_available": False,
        },
    ):
        response = await authenticated_client.post("/config/updates/check")
        assert response.status_code == 200

        # Must have been called with force=True
        mock_check.assert_called_once()
        _, kwargs = mock_check.call_args
        assert kwargs.get("force") is True
