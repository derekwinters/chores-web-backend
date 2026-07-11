"""Tests for the public, unauthenticated GET /version endpoint.

See derekwinters/chores-web-backend#27: the update-check service previously
targeted the pre-split monorepo (derekwinters/chores-web); it must target
derekwinters/chores-web-backend. GET /version is a new public endpoint,
same trust tier as /health, that surfaces the backend's own version/update
status to clients (chores-web-frontend, chores-web-android) without auth.
"""
import httpx
import pytest
from unittest.mock import AsyncMock, patch
from sqlalchemy.ext.asyncio import AsyncSession

from app.models import UpdateCheck
from app.config import APP_VERSION
from app.services.update_check_service import check_for_updates, _version_cache


@pytest.mark.asyncio
async def test_version_returns_documented_shape_with_no_prior_check(client):
    """Fresh install (no UpdateCheck row yet): documented shape, nulls for
    fields that require a successful check, not an error."""
    response = await client.get("/version")

    assert response.status_code == 200
    body = response.json()
    assert set(body.keys()) == {"version", "latest_version", "update_available", "checked_at"}
    assert body["version"] == APP_VERSION
    assert body["latest_version"] is None
    assert body["update_available"] is False
    assert body["checked_at"] is None


@pytest.mark.asyncio
async def test_version_requires_no_authorization_header(client):
    """Key regression to prevent: GET /version must work with NO Authorization
    header at all, unlike /config/updates/* which requires get_current_user."""
    response = await client.get("/version")

    assert response.status_code != 401
    assert response.status_code != 403
    assert response.status_code == 200


@pytest.mark.asyncio
async def test_version_reflects_successful_update_check(client, db: AsyncSession):
    """After a successful background/manual check recorded a newer release,
    /version should surface it and flag update_available."""
    with patch(
        "app.services.update_check_service._get_github_latest_version",
        new_callable=AsyncMock,
        return_value="99.0.0",
    ):
        await check_for_updates(db, force=True)

    response = await client.get("/version")

    assert response.status_code == 200
    body = response.json()
    assert body["version"] == APP_VERSION
    assert body["latest_version"] == "99.0.0"
    assert body["update_available"] is True
    assert body["checked_at"] is not None


@pytest.mark.asyncio
async def test_version_handles_github_api_timeout_gracefully(client, db: AsyncSession):
    """A real GitHub-side failure (timeout/rate limit/network error) at the
    HTTP layer must never surface as a 500 from /version, and must never be
    reported as a fresh/available update. httpx.AsyncClient.get is mocked to
    raise a TimeoutException, exercising the actual code path (the try/except
    inside _get_github_latest_version) rather than assuming its behavior."""
    _version_cache["latest_version"] = None
    _version_cache["cached_at"] = None

    with patch(
        "app.services.update_check_service.httpx.AsyncClient.get",
        new_callable=AsyncMock,
        side_effect=httpx.TimeoutException("simulated timeout"),
    ):
        # check_for_updates must not crash even though the GitHub fetch failed.
        await check_for_updates(db, force=True)

    response = await client.get("/version")

    assert response.status_code == 200
    body = response.json()
    assert body["update_available"] is False
    assert body["latest_version"] is None


@pytest.mark.asyncio
async def test_version_after_failed_fetch_returns_null_not_stale(client, db: AsyncSession):
    """Simulate the real (non-raising) failure path: _get_github_latest_version
    returns None on timeout/non-200 (its actual documented behavior). /version
    must not crash and must not claim an update is available."""
    update_check = UpdateCheck(
        current_version=APP_VERSION,
        check_enabled=True,
        check_interval_hours=24,
    )
    db.add(update_check)
    await db.commit()

    with patch(
        "app.services.update_check_service._get_github_latest_version",
        new_callable=AsyncMock,
        return_value=None,
    ):
        await check_for_updates(db, force=True)

    response = await client.get("/version")

    assert response.status_code == 200
    body = response.json()
    assert body["update_available"] is False
    assert body["latest_version"] is None
    # checked_at reflects the attempt happened, even though no version data
    # was obtained — this is the "attempted, nothing new to report" state.
    assert body["checked_at"] is not None
