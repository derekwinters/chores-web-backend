from datetime import datetime, date, timedelta
from typing import Optional
from fastapi import APIRouter, Depends, Query
from sqlalchemy import select, delete
from sqlalchemy.ext.asyncio import AsyncSession
from pydantic import BaseModel

from ..database import get_db
from ..models import ChoreLog
from ..schemas import ChoreLogOut
from ..dependencies import get_current_user, require_admin

router = APIRouter(prefix="/log", tags=["log"])

_log_retention_days = 90


class RetentionSettings(BaseModel):
    retention_days: int


@router.get("", response_model=list[ChoreLogOut])
async def get_log(
    person: Optional[str] = Query(None),
    chore_id: Optional[str] = Query(None),
    action: Optional[str] = Query(None),
    start_date: Optional[date] = Query(None),
    end_date: Optional[date] = Query(None),
    current_user: str = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    query = select(ChoreLog).order_by(ChoreLog.timestamp.desc())

    if person:
        query = query.where(ChoreLog.person.ilike(person))
    if chore_id:
        query = query.where(ChoreLog.chore_id == int(chore_id))
    if action:
        query = query.where(ChoreLog.action == action)
    if start_date:
        query = query.where(ChoreLog.timestamp >= datetime.combine(start_date, datetime.min.time()))
    if end_date:
        query = query.where(ChoreLog.timestamp <= datetime.combine(end_date, datetime.max.time()))

    result = await db.execute(query)
    return result.scalars().all()


@router.get("/retention", response_model=RetentionSettings)
async def get_retention(
    current_user: str = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    return RetentionSettings(retention_days=_log_retention_days)


@router.post("/retention", response_model=RetentionSettings)
async def set_retention(
    settings: RetentionSettings,
    current_user: str = Depends(require_admin),
    db: AsyncSession = Depends(get_db),
):
    global _log_retention_days
    _log_retention_days = max(1, settings.retention_days)

    cutoff_date = datetime.now() - timedelta(days=_log_retention_days)
    await db.execute(delete(ChoreLog).where(ChoreLog.timestamp < cutoff_date))
    await db.commit()

    return RetentionSettings(retention_days=_log_retention_days)
