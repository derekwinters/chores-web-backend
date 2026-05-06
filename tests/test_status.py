"""Tests for system status endpoints."""
import pytest


async def test_db_status_endpoint(client):
    """Test /api/db-status returns ready status."""
    response = await client.get("/api/db-status")
    assert response.status_code == 200

    data = response.json()
    assert "ready" in data
    assert isinstance(data["ready"], bool)
    assert data["ready"] is True


async def test_db_status_has_ready_field(client):
    """Test /api/db-status always has ready field."""
    response = await client.get("/api/db-status")
    data = response.json()

    # Must have ready field
    assert "ready" in data
    # ready should be boolean
    assert isinstance(data["ready"], bool)
