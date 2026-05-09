from fastapi import APIRouter, Depends
from sqlalchemy import select
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


@router.get("", response_model=ConfigOut)
async def get_config(current_user: str = Depends(get_current_user), db: AsyncSession = Depends(get_db)):
    title = await _get_setting(db, "title", "Family Chores")
    auth_enabled = await _get_auth_enabled(db)
    timezone = await _get_timezone(db)
    due_soon_days = await _get_due_soon_days(db)
    update_check_enabled = await _get_update_check_enabled(db)
    update_check_interval = await _get_update_check_interval(db)
    return ConfigOut(
        title=title,
        auth_enabled=auth_enabled,
        timezone=timezone,
        due_soon_days=due_soon_days,
        update_check_enabled=update_check_enabled,
        update_check_interval=update_check_interval,
    )


@router.put("", response_model=ConfigOut)
async def update_config(body: ConfigUpdate, current_user: str = Depends(get_current_user), db: AsyncSession = Depends(get_db)):
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

    await db.commit()

    title = await _get_setting(db, "title", "Family Chores")
    auth_enabled = await _get_auth_enabled(db)
    timezone = await _get_timezone(db)
    due_soon_days = await _get_due_soon_days(db)
    update_check_enabled = await _get_update_check_enabled(db)
    update_check_interval = await _get_update_check_interval(db)
    return ConfigOut(
        title=title,
        auth_enabled=auth_enabled,
        timezone=timezone,
        due_soon_days=due_soon_days,
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
    await check_for_updates(db)
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
