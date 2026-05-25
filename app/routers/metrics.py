"""Prometheus metrics endpoint.

Exposes application metrics at GET /metrics in Prometheus text format.
Public endpoint — no authentication required.
Process metrics (CPU, memory, file descriptors) and HTTP request metrics
are provided automatically by prometheus_client and starlette_prometheus.
"""
from datetime import date, timedelta, timezone, datetime

import prometheus_client
from fastapi import APIRouter, Depends
from fastapi.responses import Response
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from ..database import get_db
from ..models import Chore, Person, PointsLog, Settings

router = APIRouter(tags=["metrics"])

# ---------------------------------------------------------------------------
# Gauge definitions — all defined at module level so they survive across
# requests and accumulate values correctly.
# ---------------------------------------------------------------------------

_chores_total = prometheus_client.Gauge(
    "chores_total",
    "Total chores grouped by state and disabled flag",
    ["state", "disabled"],
)

_chores_due_now_total = prometheus_client.Gauge(
    "chores_due_now_total",
    "Chores where state='due'",
)

_chores_due_soon_total = prometheus_client.Gauge(
    "chores_due_soon_total",
    "Chores where next_due <= today + due_soon_days",
)

_chores_due_now_by_person = prometheus_client.Gauge(
    "chores_due_now_by_person",
    "Due chores grouped by current_assignee",
    ["person"],
)

_people_total = prometheus_client.Gauge(
    "people_total",
    "Total registered user count",
)

_points_awarded_total = prometheus_client.Gauge(
    "points_awarded_total",
    "Sum of all PointsLog point entries",
)

_chore_completions_by_person = prometheus_client.Gauge(
    "chore_completions_by_person",
    "Chore completions per person for 7d and 30d windows",
    ["person", "window"],
)


async def _get_due_soon_days(db: AsyncSession) -> int:
    """Read due_soon_days from Settings; default 3."""
    result = await db.execute(
        select(Settings).where(Settings.key == "due_soon_days")
    )
    row = result.scalar_one_or_none()
    return int(row.value) if row else 3


async def _collect_metrics(db: AsyncSession) -> None:
    """Query the database and update all application gauges."""
    today = date.today()
    now = datetime.now(timezone.utc)

    # chores_total — group by (state, disabled)
    chore_counts = await db.execute(
        select(Chore.state, Chore.disabled, func.count()).group_by(Chore.state, Chore.disabled)
    )
    # Clear current label combinations before repopulating
    _chores_total.clear()
    for state, disabled, count in chore_counts.all():
        _chores_total.labels(state=state, disabled=str(disabled).lower()).set(count)

    # chores_due_now_total
    due_now = await db.execute(
        select(func.count()).select_from(Chore).where(Chore.state == "due")
    )
    _chores_due_now_total.set(due_now.scalar_one())

    # chores_due_soon_total
    due_soon_days = await _get_due_soon_days(db)
    due_soon_cutoff = today + timedelta(days=due_soon_days)
    due_soon = await db.execute(
        select(func.count()).select_from(Chore).where(
            Chore.next_due <= due_soon_cutoff
        )
    )
    _chores_due_soon_total.set(due_soon.scalar_one())

    # chores_due_now_by_person — due chores grouped by current_assignee
    by_person = await db.execute(
        select(Chore.current_assignee, func.count())
        .where(Chore.state == "due")
        .group_by(Chore.current_assignee)
    )
    _chores_due_now_by_person.clear()
    for assignee, count in by_person.all():
        person_label = assignee or "unassigned"
        _chores_due_now_by_person.labels(person=person_label).set(count)

    # people_total
    people_count = await db.execute(select(func.count()).select_from(Person))
    _people_total.set(people_count.scalar_one())

    # points_awarded_total
    points_sum = await db.execute(select(func.sum(PointsLog.points)))
    _points_awarded_total.set(points_sum.scalar_one() or 0)

    # chore_completions_by_person — 7d and 30d windows
    _chore_completions_by_person.clear()
    for window_label, days in [("7d", 7), ("30d", 30)]:
        cutoff = now - timedelta(days=days)
        completions = await db.execute(
            select(PointsLog.person, func.count())
            .where(PointsLog.completed_at >= cutoff)
            .group_by(PointsLog.person)
        )
        for person, count in completions.all():
            _chore_completions_by_person.labels(person=person, window=window_label).set(count)


@router.get("/metrics", include_in_schema=False)
async def metrics(db: AsyncSession = Depends(get_db)):
    """Return Prometheus metrics in text format.

    Public endpoint — no authentication required. Process metrics are
    collected automatically by prometheus_client; application metrics are
    queried from the database on each scrape.
    """
    await _collect_metrics(db)
    data = prometheus_client.generate_latest()
    return Response(
        content=data,
        media_type=prometheus_client.CONTENT_TYPE_LATEST,
    )
