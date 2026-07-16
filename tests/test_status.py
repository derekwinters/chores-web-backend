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


async def test_status_root_returns_versions(client):
    """GET /status/ surfaces the app version, current API major version, and
    the enumerable list of supported API versions (issue #16).

    This is unversioned infrastructure — it must live at /status/ with NO
    /api/v1/ (or /v1/) prefix, so a client can negotiate the API surface
    before committing to a versioned path.
    """
    from app.config import APP_VERSION, API_VERSION, SUPPORTED_API_VERSIONS

    response = await client.get("/status/")
    assert response.status_code == 200

    data = response.json()
    assert data["version"] == APP_VERSION
    assert data["api_version"] == API_VERSION
    assert data["versions"] == SUPPORTED_API_VERSIONS
    # The current major version must be one of the enumerated versions.
    assert data["api_version"] in data["versions"]
    assert isinstance(data["versions"], list)
    assert data["versions"] == ["v1"]


async def test_status_root_is_unversioned(client):
    """Regression guard: the status version endpoint must NOT be reachable
    under a versioned prefix — status endpoints are unversioned per CLAUDE.md.
    """
    assert (await client.get("/status/")).status_code == 200
    assert (await client.get("/v1/status/")).status_code == 404
    assert (await client.get("/api/v1/status/")).status_code == 404


async def test_status_root_requires_no_authorization(client):
    """The status endpoint is public infrastructure like /status/db-status —
    it must work with no Authorization header."""
    response = await client.get("/status/")
    assert response.status_code not in (401, 403)
    assert response.status_code == 200


async def test_db_status_response_format(client):
    """Test /status/db-status response has correct fields."""
    from app.database import set_db_status, DatabaseStatus

    # Simulate successful initialization
    set_db_status(DatabaseStatus.READY)

    response = await client.get("/status/db-status")
    data = response.json()

    assert data["status"] == "ready"
    assert data["migrations_in_progress"] is False
