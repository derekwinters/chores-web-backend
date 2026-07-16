"""Tests for issue #14 — reliable update-check scheduling and post-split
release-source resolution.

Two concerns are covered:

1. Scheduling reliability. The periodic update-check job must be registered
   with an intentional misfire grace window and coalescing, and must run
   promptly at startup so a process restart (which resets the in-memory
   jobstore's interval clock) doesn't silently defer the check a fresh 24h.

2. Post-split release-source resolution. "Latest version" must be resolved
   across the split release locations (chores-web-backend and
   chores-web-frontend), not the old monorepo (derekwinters/chores-web).
"""
from datetime import datetime, timedelta
from unittest.mock import AsyncMock, MagicMock, patch

import pytest
from sqlalchemy.ext.asyncio import AsyncSession

from app.models import UpdateCheck
from app.services.update_check_service import (
    GITHUB_API_URL,
    RELEASE_SOURCES,
    _get_github_latest_version,
    _version_cache,
    get_update_status,
)


# --- Scheduling reliability -------------------------------------------------

@pytest.mark.asyncio
async def test_update_check_job_registered_with_misfire_coalesce_and_prompt_run():
    """The periodic update-check job must be configured so a briefly-down or
    busy process catches a missed cycle instead of silently skipping it, and
    must run promptly at startup rather than waiting a fresh 24h interval."""
    from app.services import scheduler as sched_mod

    sched_mod.start_scheduler(due_hour=6, timezone="UTC")
    try:
        job = sched_mod.scheduler.get_job("periodic_update_check")
        assert job is not None

        # Intentional misfire grace window (>= 1h) so a briefly-down process
        # still runs the missed cycle when it comes back up.
        assert job.misfire_grace_time is not None
        assert job.misfire_grace_time >= 3600

        # Collapse multiple missed fires into a single catch-up run.
        assert job.coalesce is True

        # Runs promptly at startup (survives restart) rather than 24h out.
        assert job.next_run_time is not None
        now = datetime.now(job.next_run_time.tzinfo)
        assert job.next_run_time <= now + timedelta(minutes=1)

        # The next-run time must be observable via the helper.
        assert sched_mod.get_update_check_next_run() == job.next_run_time
    finally:
        sched_mod.stop_scheduler()


@pytest.mark.asyncio
async def test_get_update_status_surfaces_next_scheduled_run(db: AsyncSession):
    """Last-checked and next-scheduled-run times must both be observable in the
    update-check status payload."""
    update_check = UpdateCheck(
        current_version="1.0.0",
        check_enabled=True,
        check_interval_hours=24,
    )
    db.add(update_check)
    await db.commit()

    status = await get_update_status(db)

    assert "last_checked_at" in status
    assert "next_scheduled_run" in status


# --- Post-split release-source resolution -----------------------------------

def test_release_sources_target_split_repos_not_monorepo():
    urls = list(RELEASE_SOURCES.values())
    assert any("chores-web-backend" in u for u in urls), urls
    assert any("chores-web-frontend" in u for u in urls), urls
    # The old monorepo release location must not be used.
    assert all("/repos/derekwinters/chores-web/releases" not in u for u in urls), urls
    # Backend source constant stays consistent with RELEASE_SOURCES.
    assert GITHUB_API_URL in urls


@pytest.mark.asyncio
async def test_get_latest_version_resolves_max_across_split_repos():
    """The checker queries both split repos and reports the highest semver."""
    _version_cache["latest_version"] = None
    _version_cache["cached_at"] = None

    async def fake_get(url):
        resp = MagicMock()
        resp.status_code = 200
        if "chores-web-frontend" in url:
            resp.json.return_value = {"tag_name": "v3.1.0"}
        else:
            resp.json.return_value = {"tag_name": "v2.4.0"}
        return resp

    mock_client = AsyncMock()
    mock_client.get = AsyncMock(side_effect=fake_get)
    mock_client.__aenter__.return_value = mock_client
    mock_client.__aexit__.return_value = None

    with patch(
        "app.services.update_check_service.httpx.AsyncClient",
        return_value=mock_client,
    ):
        version = await _get_github_latest_version(force=True)

    called_urls = [call.args[0] for call in mock_client.get.call_args_list]
    assert any("chores-web-backend" in u for u in called_urls), called_urls
    assert any("chores-web-frontend" in u for u in called_urls), called_urls
    # Frontend (3.1.0) is newer than backend (2.4.0).
    assert version == "3.1.0"
