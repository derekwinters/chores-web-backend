import logging

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy import select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.ext.asyncio import AsyncSession

from ..database import get_db
from ..schemas import ConfigOut, ConfigUpdate, UpdateCheckStatus
from ..dependencies import get_current_user
from ..models import Settings, UpdateCheck
from ..services.update_check_service import (
    check_for_updates,
    get_update_status,
    configure_update_check,
)
from ..services.scheduler import reschedule_transition

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/config", tags=["config"])


async def _get_setting(db: AsyncSession, key: str, default: str) -> str:
    """Get a setting from database. Return default if not set."""
    result = await db.execute(select(Settings).where(Settings.key == key))
    settings_row = result.scalar_one_or_none()
    return settings_row.value if settings_row else default


async def _get_auth_enabled(db: AsyncSession) -> bool:
    """Get auth_enabled setting from database. Default to True if not set."""
    result = await db.execute(select(Settings).where(Settings.key == "auth_enabled"))
    settings_row = result.scalar_one_or_none()
    return settings_row and settings_row.value.lower() == "true" if settings_row else True


async def _get_timezone(db: AsyncSession) -> str:
    """Get timezone setting from database. Default to UTC if not set."""
    return await _get_setting(db, "timezone", "UTC")


async def _get_due_soon_days(db: AsyncSession) -> int:
    """Get due_soon_days setting from database. Default to 3 if not set."""
    result = await db.execute(select(Settings).where(Settings.key == "due_soon_days"))
    settings_row = result.scalar_one_or_none()
    return int(settings_row.value) if settings_row else 3


async def _get_update_check_enabled(db: AsyncSession) -> bool:
    """Get update check enabled setting from database. Default to True if not set."""
    result = await db.execute(select(Settings).where(Settings.key == "update_check_enabled"))
    settings_row = result.scalar_one_or_none()
    return settings_row and settings_row.value.lower() == "true" if settings_row else True


async def _get_update_check_interval(db: AsyncSession) -> int:
    """Get update check interval setting from database. Default to 24 if not set."""
    result = await db.execute(select(Settings).where(Settings.key == "update_check_interval"))
    settings_row = result.scalar_one_or_none()
    return int(settings_row.value) if settings_row else 24


async def _get_due_time_hour(db: AsyncSession) -> int:
    """Get due_time_hour setting from database. Default to 6 if not set."""
    result = await db.execute(select(Settings).where(Settings.key == "due_time_hour"))
    settings_row = result.scalar_one_or_none()
    return int(settings_row.value) if settings_row else 6


@router.get("", response_model=ConfigOut)
async def get_config(current_user: str = Depends(get_current_user), db: AsyncSession = Depends(get_db)):
    title = await _get_setting(db, "title", "Family Chores")
    auth_enabled = await _get_auth_enabled(db)
    timezone = await _get_timezone(db)
    due_soon_days = await _get_due_soon_days(db)
    due_time_hour = await _get_due_time_hour(db)
    update_check_enabled = await _get_update_check_enabled(db)
    update_check_interval = await _get_update_check_interval(db)
    return ConfigOut(
        title=title,
        auth_enabled=auth_enabled,
        timezone=timezone,
        due_soon_days=due_soon_days,
        due_time_hour=due_time_hour,
        update_check_enabled=update_check_enabled,
        update_check_interval=update_check_interval,
    )


@router.put("", response_model=ConfigOut)
async def update_config(body: ConfigUpdate, current_user: str = Depends(get_current_user), db: AsyncSession = Depends(get_db)):
    should_reschedule = body.due_time_hour is not None or body.timezone is not None

    if body.title is not None:
        result = await db.execute(select(Settings).where(Settings.key == "title"))
        settings_row = result.scalar_one_or_none()
        if settings_row:
            settings_row.value = body.title
        else:
            settings_row = Settings(key="title", value=body.title)
            db.add(settings_row)

    if body.auth_enabled is not None:
        result = await db.execute(select(Settings).where(Settings.key == "auth_enabled"))
        settings_row = result.scalar_one_or_none()
        if settings_row:
            settings_row.value = str(body.auth_enabled).lower()
        else:
            settings_row = Settings(key="auth_enabled", value=str(body.auth_enabled).lower())
            db.add(settings_row)

    if body.timezone is not None:
        result = await db.execute(select(Settings).where(Settings.key == "timezone"))
        settings_row = result.scalar_one_or_none()
        if settings_row:
            settings_row.value = body.timezone
        else:
            settings_row = Settings(key="timezone", value=body.timezone)
            db.add(settings_row)

    if body.due_soon_days is not None:
        result = await db.execute(select(Settings).where(Settings.key == "due_soon_days"))
        settings_row = result.scalar_one_or_none()
        if settings_row:
            settings_row.value = str(body.due_soon_days)
        else:
            settings_row = Settings(key="due_soon_days", value=str(body.due_soon_days))
            db.add(settings_row)

    if body.due_time_hour is not None:
        result = await db.execute(select(Settings).where(Settings.key == "due_time_hour"))
        settings_row = result.scalar_one_or_none()
        if settings_row:
            settings_row.value = str(body.due_time_hour)
        else:
            settings_row = Settings(key="due_time_hour", value=str(body.due_time_hour))
            db.add(settings_row)

    if body.update_check_enabled is not None:
        result = await db.execute(select(Settings).where(Settings.key == "update_check_enabled"))
        settings_row = result.scalar_one_or_none()
        if settings_row:
            settings_row.value = str(body.update_check_enabled).lower()
        else:
            settings_row = Settings(key="update_check_enabled", value=str(body.update_check_enabled).lower())
            db.add(settings_row)

    if body.update_check_interval is not None:
        result = await db.execute(select(Settings).where(Settings.key == "update_check_interval"))
        settings_row = result.scalar_one_or_none()
        if settings_row:
            settings_row.value = str(body.update_check_interval)
        else:
            settings_row = Settings(key="update_check_interval", value=str(body.update_check_interval))
            db.add(settings_row)

    try:
        await db.commit()
    except IntegrityError as e:
        await db.rollback()
        if e.orig and "UniqueViolationError" in type(e.orig).__name__:
            logger.warning("Unique constraint violation updating config")
            raise HTTPException(status_code=409, detail="Conflict updating config")
        logger.exception("Unexpected integrity error updating config")
        raise HTTPException(status_code=500, detail="Database error while updating config")
    except Exception:
        await db.rollback()
        logger.exception("Unexpected error updating config")
        raise

    title = await _get_setting(db, "title", "Family Chores")
    auth_enabled = await _get_auth_enabled(db)
    timezone = await _get_timezone(db)
    due_soon_days = await _get_due_soon_days(db)
    due_time_hour = await _get_due_time_hour(db)
    update_check_enabled = await _get_update_check_enabled(db)
    update_check_interval = await _get_update_check_interval(db)

    if should_reschedule:
        reschedule_transition(due_time_hour, timezone)

    return ConfigOut(
        title=title,
        auth_enabled=auth_enabled,
        timezone=timezone,
        due_soon_days=due_soon_days,
        due_time_hour=due_time_hour,
        update_check_enabled=update_check_enabled,
        update_check_interval=update_check_interval,
    )


@router.get("/updates/status", response_model=UpdateCheckStatus)
async def get_update_check_status(
    current_user: str = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """Get the current update check status (admin only)."""
    return await get_update_status(db)


@router.post("/updates/check", response_model=UpdateCheckStatus)
async def trigger_update_check(
    current_user: str = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """Manually trigger an update check (admin only)."""
    await check_for_updates(db, force=True)
    return await get_update_status(db)


@router.put("/updates/config")
async def configure_update_checking(
    enabled: bool = None,
    interval_hours: int = None,
    current_user: str = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """Configure update checking settings (admin only)."""
    return await configure_update_check(db, enabled=enabled, interval_hours=interval_hours)
