from fastapi import APIRouter, Depends
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from ..database import get_db
from ..schemas import ConfigOut, ConfigUpdate
from ..dependencies import get_current_user
from ..models import Settings

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


@router.get("", response_model=ConfigOut)
async def get_config(current_user: str = Depends(get_current_user), db: AsyncSession = Depends(get_db)):
    title = await _get_setting(db, "title", "Family Chores")
    auth_enabled = await _get_auth_enabled(db)
    timezone = await _get_timezone(db)
    return ConfigOut(title=title, auth_enabled=auth_enabled, timezone=timezone)


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
            settings_row.value = str(body.auth_enabled)
        else:
            settings_row = Settings(key="auth_enabled", value=str(body.auth_enabled))
            db.add(settings_row)

    if body.timezone is not None:
        result = await db.execute(select(Settings).where(Settings.key == "timezone"))
        settings_row = result.scalar_one_or_none()
        if settings_row:
            settings_row.value = body.timezone
        else:
            settings_row = Settings(key="timezone", value=body.timezone)
            db.add(settings_row)

    await db.commit()

    title = await _get_setting(db, "title", "Family Chores")
    auth_enabled = await _get_auth_enabled(db)
    timezone = await _get_timezone(db)
    return ConfigOut(title=title, auth_enabled=auth_enabled, timezone=timezone)
