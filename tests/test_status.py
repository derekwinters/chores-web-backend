"""Tests for system status endpoints."""
import pytest


async def test_db_status_endpoint(client):
    """Test /status/db-status returns database status."""
    response = await client.get("/status/db-status")
    assert response.status_code == 200

    data = response.json()
    assert "status" in data
    assert data["status"] in ["initializing", "ready", "error"]
    assert "migrations_in_progress" in data
    assert isinstance(data["migrations_in_progress"], bool)


async def test_db_status_response_format(client):
    """Test /status/db-status response has correct fields."""
    from app.database import set_db_status, DatabaseStatus

    # Simulate successful initialization
    set_db_status(DatabaseStatus.READY)

    response = await client.get("/status/db-status")
    data = response.json()

    assert data["status"] == "ready"
    assert data["migrations_in_progress"] is False
