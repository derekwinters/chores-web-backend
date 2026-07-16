import logging
from datetime import datetime, timedelta, timezone

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy import func, select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.ext.asyncio import AsyncSession

from ..database import get_db
from ..models import PointsLog, Person, ChoreLog
from ..schemas import LeaderboardEntry, PointAwardCreate, PointsLogOut, PointsSummaryEntry, UserStatsOut
from ..dependencies import get_current_user, require_admin
from ..services.logging import log_person_change

logger = logging.getLogger(__name__)

# Sentinel chore_id for a Credit that is not tied to any Chore (a one-time
# admin award). Mirrors the chore_id=0 sentinel the Activity Log uses for
# non-chore (UserLog) entries.
AWARD_CHORE_ID = 0

router = APIRouter(prefix="/points", tags=["points"])


def _as_aware(dt: datetime) -> datetime:
    """Return dt as timezone-aware; assumes UTC if naive."""
    return dt if dt.tzinfo else dt.replace(tzinfo=timezone.utc)


@router.get("", response_model=list[LeaderboardEntry])
async def leaderboard(current_user: str = Depends(get_current_user), db: AsyncSession = Depends(get_db)):
    result = await db.execute(
        select(PointsLog.person, func.sum(PointsLog.points).label("total_points"))
        .group_by(PointsLog.person)
        .order_by(func.sum(PointsLog.points).desc())
    )
    return [LeaderboardEntry(person=row.person, total_points=row.total_points) for row in result]


@router.post("/award", response_model=PointsLogOut, status_code=201)
async def award_points(
    body: PointAwardCreate,
    current_user: str = Depends(require_admin),
    db: AsyncSession = Depends(get_db),
):
    """Admin-only: award one-time points (a Credit) to a person with a required
    reason, independent of any Chore Completion.

    Writes an append-only Points Log entry (the Credit) and an Activity Log
    entry (via UserLog) recording who granted the points, to whom, the amount,
    and the reason.
    """
    result = await db.execute(select(Person).where(Person.username == body.person))
    person = result.scalar_one_or_none()
    if not person:
        raise HTTPException(status_code=404, detail="Person not found")

    now = datetime.now(timezone.utc)
    credit = PointsLog(
        person=person.username,
        points=body.points,
        chore_id=AWARD_CHORE_ID,
        completed_at=now,
    )
    db.add(credit)

    # Keep the person's running total consistent with Completion credits.
    person.points += body.points
    db.add(person)

    # Activity Log entry (UserLog) for auditability: who granted, to whom,
    # amount, and reason. For a points_awarded entry, new_value carries the
    # awarded amount and old_value carries the reason.
    await log_person_change(
        person_id=person.id,
        person_name=person.name,
        action="points_awarded",
        changed_by=current_user,
        db=db,
        field_name="points",
        old_value=body.reason,
        new_value=str(body.points),
    )

    try:
        await db.commit()
        await db.refresh(credit)
    except IntegrityError:
        await db.rollback()
        logger.exception("Integrity error awarding points to %s", body.person)
        raise HTTPException(status_code=500, detail="Database error while awarding points")
    except Exception:
        await db.rollback()
        logger.exception("Unexpected error awarding points to %s", body.person)
        raise

    return credit


@router.get("/summary", response_model=list[PointsSummaryEntry])
async def points_summary(current_user: str = Depends(get_current_user), db: AsyncSession = Depends(get_db)):
    """7-day and 30-day point totals for every person, in one query."""
    now = datetime.now(timezone.utc)
    cutoff_7d = now - timedelta(days=7)
    cutoff_30d = now - timedelta(days=30)

    people_result = await db.execute(select(Person.username).order_by(Person.username))
    people = [row[0] for row in people_result]

    log_result = await db.execute(
        select(PointsLog).where(PointsLog.completed_at >= cutoff_30d)
    )
    logs = log_result.scalars().all()

    totals: dict[str, dict] = {p: {"points_7d": 0, "points_30d": 0} for p in people}
    for log in logs:
        if log.person not in totals:
            totals[log.person] = {"points_7d": 0, "points_30d": 0}
        totals[log.person]["points_30d"] += log.points
        if _as_aware(log.completed_at) >= cutoff_7d:
            totals[log.person]["points_7d"] += log.points

    return [
        PointsSummaryEntry(person=p, points_7d=totals[p]["points_7d"], points_30d=totals[p]["points_30d"])
        for p in people
    ]


@router.get("/stats/{person}", response_model=UserStatsOut)
async def user_stats(person: str, current_user: str = Depends(get_current_user), db: AsyncSession = Depends(get_db)):
    now = datetime.now(timezone.utc)
    cutoff_7d = now - timedelta(days=7)
    cutoff_30d = now - timedelta(days=30)

    result = await db.execute(
        select(PointsLog).where(PointsLog.person == person)
    )
    logs = result.scalars().all()

    total_points = sum(log.points for log in logs)
    points_7d = sum(log.points for log in logs if _as_aware(log.completed_at) >= cutoff_7d)
    points_30d = sum(log.points for log in logs if _as_aware(log.completed_at) >= cutoff_30d)

    log_result = await db.execute(
        select(ChoreLog).where(ChoreLog.person == person)
    )
    chore_logs = log_result.scalars().all()

    completed_count = sum(1 for log in chore_logs if log.action == "completed")
    skipped_count = sum(1 for log in chore_logs if log.action == "skipped")

    person_result = await db.execute(
        select(Person).where(Person.username == person)
    )
    person_obj = person_result.scalar_one_or_none()
    points_redeemed = person_obj.points_redeemed if person_obj else 0
    display_points = total_points - points_redeemed
    display_name = person_obj.name if person_obj else person

    return UserStatsOut(
        name=display_name,
        total_points=total_points,
        display_points=display_points,
        points_7d=points_7d,
        points_30d=points_30d,
        completed_count=completed_count,
        skipped_count=skipped_count,
    )


@router.get("/{person}", response_model=list[PointsLogOut])
async def person_history(person: str, current_user: str = Depends(get_current_user), db: AsyncSession = Depends(get_db)):
    result = await db.execute(
        select(PointsLog)
        .where(PointsLog.person == person)
        .order_by(PointsLog.completed_at.desc())
    )
    return result.scalars().all()
