import logging
from datetime import datetime, date, timedelta
from typing import Optional
from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy import select, delete
from sqlalchemy.exc import IntegrityError
from sqlalchemy.ext.asyncio import AsyncSession
from pydantic import BaseModel

from ..database import get_db
from ..models import ChoreLog, UserLog, AuthLog
from ..schemas import ChoreLogOut
from ..dependencies import get_current_user, require_admin

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/log", tags=["log"])

_log_retention_days = 90


class RetentionSettings(BaseModel):
    retention_days: int


def _user_log_to_chore_log_out(entry: UserLog) -> ChoreLogOut:
    """Convert a UserLog row into ChoreLogOut shape for the unified log response."""
    return ChoreLogOut(
        id=entry.id,
        chore_id=0,
        chore_name=f"Person: {entry.person_name}",
        person=entry.changed_by,
        action=entry.action,
        timestamp=entry.timestamp,
        reassigned_to=None,
        field_name=entry.field_name,
        old_value=entry.old_value,
        new_value=entry.new_value,
    )


@router.get("", response_model=list[ChoreLogOut])
async def get_log(
    person: Optional[str] = Query(None),
    chore_id: Optional[str] = Query(None),
    action: Optional[str] = Query(None),
    actions: Optional[list[str]] = Query(None),
    start_date: Optional[date] = Query(None),
    end_date: Optional[date] = Query(None),
    current_user: str = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    # --- ChoreLog query ---
    chore_query = select(ChoreLog)

    if person:
        chore_query = chore_query.where(ChoreLog.person.ilike(person))
    if chore_id:
        # chore_id=0 is the UserLog sentinel — exclude it from chore query
        chore_query = chore_query.where(ChoreLog.chore_id == int(chore_id))
    if action:
        chore_query = chore_query.where(ChoreLog.action == action)
    if actions:
        chore_query = chore_query.where(ChoreLog.action.in_(actions))
    if start_date:
        chore_query = chore_query.where(ChoreLog.timestamp >= datetime.combine(start_date, datetime.min.time()))
    if end_date:
        chore_query = chore_query.where(ChoreLog.timestamp <= datetime.combine(end_date, datetime.max.time()))

    chore_result = await db.execute(chore_query)
    chore_entries = list(chore_result.scalars().all())

    # --- UserLog query (skip when a specific real chore_id is requested) ---
    user_entries: list[ChoreLogOut] = []
    if not chore_id or int(chore_id) == 0:
        user_query = select(UserLog)

        if person:
            user_query = user_query.where(UserLog.changed_by.ilike(person))
        if action:
            user_query = user_query.where(UserLog.action == action)
        if actions:
            user_query = user_query.where(UserLog.action.in_(actions))
        if start_date:
            user_query = user_query.where(UserLog.timestamp >= datetime.combine(start_date, datetime.min.time()))
        if end_date:
            user_query = user_query.where(UserLog.timestamp <= datetime.combine(end_date, datetime.max.time()))

        user_result = await db.execute(user_query)
        user_entries = [_user_log_to_chore_log_out(e) for e in user_result.scalars().all()]

    # Merge and sort descending by timestamp
    chore_outs = [ChoreLogOut.model_validate(e) for e in chore_entries]
    combined = chore_outs + user_entries
    combined.sort(key=lambda e: e.timestamp, reverse=True)
    return combined


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
    await db.execute(delete(UserLog).where(UserLog.timestamp < cutoff_date))
    await db.execute(delete(AuthLog).where(AuthLog.timestamp < cutoff_date))
    try:
        await db.commit()
    except IntegrityError as e:
        await db.rollback()
        if e.orig and "UniqueViolationError" in type(e.orig).__name__:
            logger.warning("Unique constraint violation setting log retention")
            raise HTTPException(status_code=409, detail="Conflict setting log retention")
        logger.exception("Unexpected integrity error setting log retention")
        raise HTTPException(status_code=500, detail="Database error while setting log retention")
    except Exception:
        await db.rollback()
        logger.exception("Unexpected error setting log retention")
        raise

    return RetentionSettings(retention_days=_log_retention_days)
