import logging
import httpx
from datetime import datetime, timedelta
from typing import Optional
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from ..models import UpdateCheck
from ..config import APP_VERSION

logger = logging.getLogger(__name__)

# GitHub API endpoint for releases
GITHUB_API_URL = "https://api.github.com/repos/derekwinters/chores-web/releases/latest"

# In-memory cache for version info
_version_cache = {
    "latest_version": None,
    "cached_at": None,
    "cache_ttl_seconds": 3600,  # 1 hour cache
}


async def _get_github_latest_version(timeout: int = 5, force: bool = False) -> Optional[str]:
    """Fetch the latest release version from GitHub API with caching."""
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

    try:
        async with httpx.AsyncClient(timeout=timeout) as client:
            response = await client.get(GITHUB_API_URL)
            if response.status_code == 200:
                data = response.json()
                tag_name = data.get("tag_name", "").lstrip("v")
                _version_cache["latest_version"] = tag_name
                _version_cache["cached_at"] = now
                logger.info(f"Fetched latest version from GitHub: {tag_name}")
                return tag_name
            else:
                logger.warning(f"GitHub API returned status {response.status_code}")
                return None
    except httpx.TimeoutException:
        logger.warning("GitHub API request timed out")
        return None
    except Exception as e:
        logger.error(f"Unexpected error fetching GitHub version: {e}")
        return None


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

    return {
        "current_version": APP_VERSION,
        "latest_version": update_check.latest_version,
        "last_checked_at": update_check.last_checked_at,
        "check_enabled": update_check.check_enabled,
        "check_interval_hours": update_check.check_interval_hours,
        "update_available": update_available,
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


