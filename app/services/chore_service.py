from __future__ import annotations

import re
from datetime import date, datetime, timezone
from typing import Optional

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from ..models import Chore, PointsLog, ChoreLog
from ..scheduling import build_schedule

CHANGE_COMPLETED = "completed"
CHANGE_SKIPPED = "skipped"
CHANGE_REASSIGNED = "reassigned"
CHANGE_FORCED_DUE = "forced_due"
CHANGE_MARKED_DUE = "marked_due"
CHANGE_CREATED = "created"
CHANGE_DELETED = "deleted"


def _slugify(name: str) -> str:
    return re.sub(r"[^a-z0-9]+", "_", name.lower()).strip("_")


def _now() -> datetime:
    return datetime.now(timezone.utc)


def compute_age(chore: Chore) -> Optional[int]:
    if chore.next_due is None:
        return None
    return (date.today() - chore.next_due).days


def compute_schedule_summary(chore: Chore) -> str:
    config = dict(chore.schedule_config)
    config["type"] = chore.schedule_type
    try:
        return build_schedule(config).summary()
    except Exception:
        return ""


def compute_next_assignee(chore: Chore) -> Optional[str]:
    if chore.assignment_type != "rotating" or not chore.eligible_people:
        return None
    next_idx = (chore.rotation_index + 1) % len(chore.eligible_people)
    return chore.eligible_people[next_idx]


def apply_assignment_state(
    chore: Chore,
    *,
    assignment_type: Optional[str] = None,
    eligible_people: Optional[list[str]] = None,
    assignee: Optional[str] = None,
    current_assignee: Optional[str] = None,
    next_assignee: Optional[str] = None,
) -> None:
    target_assignment_type = assignment_type or chore.assignment_type
    target_eligible_people = eligible_people if eligible_people is not None else list(chore.eligible_people or [])
    target_assignee = assignee if assignee is not None else chore.assignee
    target_current_assignee = current_assignee if current_assignee is not None else chore.current_assignee

    if target_assignment_type == "fixed":
        fixed_assignee = target_assignee or target_current_assignee
        chore.assignee = fixed_assignee
        chore.current_assignee = fixed_assignee
        chore.rotation_index = 0
        return

    chore.assignee = target_assignee if target_assignment_type == "fixed" else None

    if target_assignment_type == "rotating":
        if not target_eligible_people:
            chore.current_assignee = None
            chore.rotation_index = 0
            return

        if current_assignee is not None and next_assignee is not None:
            chore.rotation_index = target_eligible_people.index(target_current_assignee)
            chore.current_assignee = target_current_assignee
            return

        if current_assignee is not None:
            chore.rotation_index = target_eligible_people.index(target_current_assignee)
            chore.current_assignee = target_current_assignee
            return

        if next_assignee is not None:
            next_idx = target_eligible_people.index(next_assignee)
            chore.rotation_index = (next_idx - 1) % len(target_eligible_people)
            chore.current_assignee = target_eligible_people[chore.rotation_index]
            return

        if chore.current_assignee in target_eligible_people:
            chore.rotation_index = target_eligible_people.index(chore.current_assignee)
            return

        current_idx = min(chore.rotation_index, len(target_eligible_people) - 1)
        chore.rotation_index = max(current_idx, 0)
        chore.current_assignee = target_eligible_people[chore.rotation_index]
        return

    chore.rotation_index = 0
    chore.current_assignee = target_current_assignee


def _calc_next_due(chore: Chore, from_date: Optional[date] = None) -> Optional[date]:
    config = dict(chore.schedule_config)
    config["type"] = chore.schedule_type
    schedule = build_schedule(config)
    anchor = from_date or date.today()
    return schedule.next_due(anchor)


def _initial_assignee(chore: Chore) -> Optional[str]:
    if chore.assignment_type == "fixed":
        return chore.assignee
    if chore.assignment_type == "rotating" and chore.eligible_people:
        return chore.eligible_people[0]
    return None


async def _log_action(
    chore: Chore,
    action: str,
    person: str,
    db: AsyncSession,
    reassigned_to: Optional[str] = None,
) -> None:
    log = ChoreLog(
        chore_id=chore.id,
        chore_name=chore.name,
        person=person,
        action=action,
        timestamp=_now(),
        reassigned_to=reassigned_to,
    )
    db.add(log)


async def initialize_chore(chore: Chore, db: AsyncSession) -> None:
    """Set initial state after creation."""
    chore.current_assignee = _initial_assignee(chore)
    chore.rotation_index = 0

    anchor = date.today() - __import__("datetime").timedelta(days=1)
    next_due = _calc_next_due(chore, from_date=anchor)
    chore.next_due = next_due

    if next_due is not None and next_due <= date.today():
        chore.state = "due"
    else:
        chore.state = "complete"

    db.add(chore)
    await db.commit()
    await db.refresh(chore)


async def complete_chore(
    chore: Chore,
    db: AsyncSession,
    completed_by: Optional[str] = None,
) -> Chore:
    if chore.points > 0 and completed_by:
        log = PointsLog(
            person=completed_by,
            points=chore.points,
            chore_id=chore.id,
            completed_at=_now(),
        )
        db.add(log)

    if chore.assignment_type == "rotating" and chore.eligible_people:
        chore.rotation_index = (chore.rotation_index + 1) % len(chore.eligible_people)
        chore.current_assignee = chore.eligible_people[chore.rotation_index]

    chore.next_due = _calc_next_due(chore)
    chore.state = "complete"
    chore.last_changed_at = _now()
    chore.last_changed_by = completed_by
    chore.last_change_type = CHANGE_COMPLETED
    chore.last_completed_at = _now()
    chore.last_completed_by = completed_by

    await _log_action(chore, CHANGE_COMPLETED, completed_by or "system", db)

    db.add(chore)
    await db.commit()
    await db.refresh(chore)
    return chore


async def skip_chore(chore: Chore, db: AsyncSession) -> Chore:
    chore.next_due = _calc_next_due(chore)
    chore.state = "complete"
    chore.last_changed_at = _now()
    chore.last_changed_by = None
    chore.last_change_type = CHANGE_SKIPPED

    await _log_action(chore, CHANGE_SKIPPED, "system", db)

    db.add(chore)
    await db.commit()
    await db.refresh(chore)
    return chore


async def skip_and_reassign_chore(
    chore: Chore,
    db: AsyncSession,
    assignee: Optional[str] = None,
) -> Chore:
    chore = await skip_chore(chore, db)

    if assignee:
        chore.current_assignee = assignee
        if chore.assignment_type == "rotating" and assignee in chore.eligible_people:
            chore.rotation_index = chore.eligible_people.index(assignee)
    elif chore.assignment_type == "rotating" and chore.eligible_people:
        chore.rotation_index = (chore.rotation_index + 1) % len(chore.eligible_people)
        chore.current_assignee = chore.eligible_people[chore.rotation_index]

    db.add(chore)
    await db.commit()
    await db.refresh(chore)
    return chore


async def reassign_chore(chore: Chore, db: AsyncSession, assignee: str) -> Chore:
    chore.current_assignee = assignee
    if chore.assignment_type == "rotating" and assignee in chore.eligible_people:
        chore.rotation_index = chore.eligible_people.index(assignee)
    chore.last_changed_at = _now()
    chore.last_changed_by = None
    chore.last_change_type = CHANGE_REASSIGNED

    await _log_action(chore, CHANGE_REASSIGNED, "system", db, reassigned_to=assignee)

    db.add(chore)
    await db.commit()
    await db.refresh(chore)
    return chore


async def mark_due_chore(chore: Chore, db: AsyncSession) -> Chore:
    if chore.state == "due":
        return chore
    chore.state = "due"
    chore.last_changed_at = _now()
    chore.last_changed_by = None
    chore.last_change_type = CHANGE_MARKED_DUE

    await _log_action(chore, CHANGE_MARKED_DUE, "system", db)

    db.add(chore)
    await db.commit()
    await db.refresh(chore)
    return chore


async def transition_overdue_chores(db: AsyncSession) -> int:
    """Flip complete chores to due when next_due <= today. Returns count changed."""
    today = date.today()
    result = await db.execute(
        select(Chore).where(Chore.state == "complete", Chore.next_due <= today)
    )
    chores = result.scalars().all()
    for chore in chores:
        chore.state = "due"
        chore.last_changed_at = _now()
        chore.last_change_type = CHANGE_FORCED_DUE
        await _log_action(chore, "marked_due_by_schedule", "system", db)
        db.add(chore)
    if chores:
        await db.commit()
    return len(chores)
