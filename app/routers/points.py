from datetime import datetime, timedelta, timezone

from fastapi import APIRouter, Depends
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from ..database import get_db
from ..models import PointsLog, Person, ChoreLog
from ..schemas import LeaderboardEntry, PointsLogOut, PointsSummaryEntry, UserStatsOut
from ..dependencies import get_current_user

router = APIRouter(prefix="/points", tags=["points"])


@router.get("", response_model=list[LeaderboardEntry])
async def leaderboard(current_user: str = Depends(get_current_user), db: AsyncSession = Depends(get_db)):
    result = await db.execute(
        select(PointsLog.person, func.sum(PointsLog.points).label("total_points"))
        .group_by(PointsLog.person)
        .order_by(func.sum(PointsLog.points).desc())
    )
    return [LeaderboardEntry(person=row.person, total_points=row.total_points) for row in result]


@router.get("/summary", response_model=list[PointsSummaryEntry])
async def points_summary(current_user: str = Depends(get_current_user), db: AsyncSession = Depends(get_db)):
    """7-day and 30-day point totals for every person, in one query."""
    now = datetime.now(timezone.utc)
    cutoff_7d = now - timedelta(days=7)
    cutoff_30d = now - timedelta(days=30)

    people_result = await db.execute(select(Person.name).order_by(Person.name))
    people = [row[0] for row in people_result]

    log_result = await db.execute(
        select(PointsLog).where(PointsLog.completed_at >= cutoff_30d)
    )
    logs = log_result.scalars().all()

    def _as_aware(dt: datetime) -> datetime:
        return dt if dt.tzinfo else dt.replace(tzinfo=timezone.utc)

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
    points_7d = sum(log.points for log in logs if log.completed_at >= cutoff_7d)
    points_30d = sum(log.points for log in logs if log.completed_at >= cutoff_30d)

    log_result = await db.execute(
        select(ChoreLog).where(ChoreLog.person == person)
    )
    chore_logs = log_result.scalars().all()

    completed_count = sum(1 for log in chore_logs if log.action == "completed")
    skipped_count = sum(1 for log in chore_logs if log.action == "skipped")

    person_result = await db.execute(
        select(Person).where(Person.name == person)
    )
    person_obj = person_result.scalar_one_or_none()
    points_redeemed = person_obj.points_redeemed if person_obj else 0
    display_points = total_points - points_redeemed

    return UserStatsOut(
        name=person,
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
