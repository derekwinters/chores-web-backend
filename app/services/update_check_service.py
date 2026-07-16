import logging
import httpx
from datetime import datetime, timedelta
from typing import Optional
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from ..models import UpdateCheck
from ..config import APP_VERSION

logger = logging.getLogger(__name__)

# GitHub API endpoints for releases.
#
# Post-split, "latest version" is resolved across the split release locations
# (chores-web-backend and chores-web-frontend), NOT the old monorepo
# (derekwinters/chores-web). GITHUB_API_URL is kept as the backend source of
# record; RELEASE_SOURCES enumerates every repo whose latest release counts.
BACKEND_API_URL = "https://api.github.com/repos/derekwinters/chores-web-backend/releases/latest"
FRONTEND_API_URL = "https://api.github.com/repos/derekwinters/chores-web-frontend/releases/latest"

# Backwards-compatible alias for the backend's own release source.
GITHUB_API_URL = BACKEND_API_URL

RELEASE_SOURCES = {
    "backend": BACKEND_API_URL,
    "frontend": FRONTEND_API_URL,
}


def _parse_version(value: Optional[str]):
    """Parse a dotted semver-ish string into a comparable tuple, or None."""
    if not value:
        return None
    try:
        return tuple(int(part) for part in value.split("."))
    except (ValueError, AttributeError):
        return None


def _max_version(versions) -> Optional[str]:
    """Return the highest semver string among ``versions``.

    Unparseable or empty entries are ignored. Returns None when nothing is
    parseable (e.g. every release fetch failed)."""
    best: Optional[str] = None
    best_key = None
    for version in versions:
        key = _parse_version(version)
        if key is None:
            continue
        if best_key is None or key > best_key:
            best_key = key
            best = version
    return best

# In-memory cache for version info
_version_cache = {
    "latest_version": None,
    "cached_at": None,
    "cache_ttl_seconds": 3600,  # 1 hour cache
}


async def _fetch_release_tag(client: httpx.AsyncClient, name: str, url: str) -> Optional[str]:
    """Fetch a single repo's latest release tag (stripped of a leading 'v').

    Failures (timeout, non-200, network error) are logged and return None so a
    single unreachable source can't sink resolution of the others."""
    try:
        response = await client.get(url)
        if response.status_code == 200:
            tag_name = response.json().get("tag_name", "").lstrip("v") or None
            if tag_name:
                logger.info(f"Fetched latest {name} version from GitHub: {tag_name}")
            return tag_name
        logger.warning(f"GitHub API returned status {response.status_code} for {name}")
        return None
    except httpx.TimeoutException:
        logger.warning(f"GitHub API request timed out for {name}")
        return None
    except Exception as e:
        logger.error(f"Unexpected error fetching GitHub version for {name}: {e}")
        return None


async def _get_github_latest_version(timeout: int = 5, force: bool = False) -> Optional[str]:
    """Resolve the latest release version across the split repos, with caching.

    Queries every entry in RELEASE_SOURCES (backend + frontend) and returns the
    highest semver found, so the reported "latest version" reflects the newest
    release of the split project rather than one repo in isolation."""
    now = datetime.utcnow()

    # Check if cache is still valid (bypassed when force=True)
    if (
        not force
        and _version_cache["latest_version"] is not None
        and _version_cache["cached_at"] is not None
        and (now - _version_cache["cached_at"]).total_seconds() < _version_cache["cache_ttl_seconds"]
    ):
        logger.debug("Using cached version info")
        return _version_cache["latest_version"]

    tags = []
    try:
        async with httpx.AsyncClient(timeout=timeout) as client:
            for name, url in RELEASE_SOURCES.items():
                tag = await _fetch_release_tag(client, name, url)
                if tag:
                    tags.append(tag)
    except Exception as e:
        logger.error(f"Unexpected error creating GitHub client: {e}")
        return None

    latest = _max_version(tags)
    # Only refresh the cache on a successful resolution; a total failure leaves
    # the previous (possibly None) value untouched rather than caching a miss.
    if latest is not None:
        _version_cache["latest_version"] = latest
        _version_cache["cached_at"] = now
    return latest


async def check_for_updates(db: AsyncSession, force: bool = False) -> Optional[str]:
    """Check for updates and return latest version if available."""
    result = await db.execute(select(UpdateCheck).limit(1))
    update_check = result.scalar_one_or_none()

    if not update_check:
        # Create initial record
        update_check = UpdateCheck(
            current_version=APP_VERSION,
            check_enabled=True,
            check_interval_hours=24,
        )
        db.add(update_check)
        await db.commit()
    elif update_check.current_version != APP_VERSION:
        update_check.current_version = APP_VERSION
        await db.commit()

    # Check if enough time has passed since last check (bypassed when force=True)
    if not force and update_check.last_checked_at:
        time_since_check = datetime.utcnow() - update_check.last_checked_at.replace(tzinfo=None)
        if time_since_check.total_seconds() < update_check.check_interval_hours * 3600:
            logger.debug("Update check skipped (interval not yet reached)")
            return update_check.latest_version

    # Skip check if disabled
    if not update_check.check_enabled:
        logger.debug("Update checking is disabled")
        return update_check.latest_version

    # Fetch latest version from GitHub (force bypasses in-memory version cache)
    latest_version = await _get_github_latest_version(force=force)

    # Update the record
    update_check.latest_version = latest_version
    update_check.last_checked_at = datetime.utcnow()
    await db.commit()

    return latest_version


async def get_update_status(db: AsyncSession) -> dict:
    """Get current update check status."""
    result = await db.execute(select(UpdateCheck).limit(1))
    update_check = result.scalar_one_or_none()

    if not update_check:
        # Create initial record if it doesn't exist
        update_check = UpdateCheck(
            current_version=APP_VERSION,
            check_enabled=True,
            check_interval_hours=24,
        )
        db.add(update_check)
        await db.commit()
    elif update_check.current_version != APP_VERSION:
        update_check.current_version = APP_VERSION
        await db.commit()

    # Determine if update is available
    update_available = False
    if update_check.latest_version and update_check.latest_version != update_check.current_version:
        try:
            # Simple version comparison (assumes semantic versioning)
            latest_parts = [int(x) for x in update_check.latest_version.split(".")]
            current_parts = [int(x) for x in update_check.current_version.split(".")]

            # Pad with zeros if needed
            while len(latest_parts) < len(current_parts):
                latest_parts.append(0)
            while len(current_parts) < len(latest_parts):
                current_parts.append(0)

            update_available = latest_parts > current_parts
        except (ValueError, AttributeError):
            # If version parsing fails, do simple string comparison
            update_available = update_check.latest_version != update_check.current_version

    # Surface the scheduler's next planned run so the interval is observable
    # alongside last_checked_at. Imported lazily to avoid a circular import
    # (scheduler imports check_for_updates from this module).
    try:
        from .scheduler import get_update_check_next_run

        next_scheduled_run = get_update_check_next_run()
    except Exception:
        next_scheduled_run = None

    return {
        "current_version": APP_VERSION,
        "latest_version": update_check.latest_version,
        "last_checked_at": update_check.last_checked_at,
        "check_enabled": update_check.check_enabled,
        "check_interval_hours": update_check.check_interval_hours,
        "update_available": update_available,
        "next_scheduled_run": next_scheduled_run,
    }


async def get_public_version_info(db: AsyncSession) -> dict:
    """Public-facing subset of get_update_status(), for the unauthenticated
    GET /version endpoint.

    This is a thin, read-only reshape of the same underlying (cached) status
    data used by /config/updates/status — it does not perform its own GitHub
    fetch. Because it never talks to GitHub directly, a GitHub-side failure
    (timeout, rate limit, network error) can never surface here as a 500: at
    worst, latest_version/checked_at simply reflect "no successful check yet"
    (both None, update_available False), which is the same state a fresh
    install reports and is indistinguishable-by-design from a transient
    upstream failure that hasn't been retried yet.
    """
    status = await get_update_status(db)
    return {
        "version": status["current_version"],
        "latest_version": status["latest_version"],
        "update_available": status["update_available"],
        "checked_at": status["last_checked_at"],
    }


async def configure_update_check(
    db: AsyncSession,
    enabled: Optional[bool] = None,
    interval_hours: Optional[int] = None,
) -> dict:
    """Configure update checking settings."""
    result = await db.execute(select(UpdateCheck).limit(1))
    update_check = result.scalar_one_or_none()

    if not update_check:
        update_check = UpdateCheck(
            current_version=APP_VERSION,
            check_enabled=enabled if enabled is not None else True,
            check_interval_hours=interval_hours if interval_hours is not None else 24,
        )
        db.add(update_check)
    else:
        if enabled is not None:
            update_check.check_enabled = enabled
        if interval_hours is not None:
            update_check.check_interval_hours = max(1, interval_hours)

    await db.commit()

    return await get_update_status(db)


