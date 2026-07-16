from __future__ import annotations

import logging
import re
from datetime import date, datetime, timezone
from typing import Optional

from fastapi import HTTPException
from sqlalchemy import select, update
from sqlalchemy.exc import IntegrityError
from sqlalchemy.ext.asyncio import AsyncSession

from ..models import Chore, PointsLog, ChoreLog, Person, Notification, NotificationPreference
from ..scheduling import build_schedule

logger = logging.getLogger(__name__)

CHANGE_COMPLETED = "completed"
CHANGE_SKIPPED = "skipped"
CHANGE_REASSIGNED = "reassigned"
CHANGE_FORCED_DUE = "forced_due"
CHANGE_MARKED_DUE = "marked_due"
CHANGE_CREATED = "created"
CHANGE_DELETED = "deleted"

# v1 has exactly one server-generated notification type.
NOTIFICATION_TYPE_CHORE_DUE = "chore_due"


async def normalize_points_log_persons(db: AsyncSession) -> None:
    """Normalize legacy PointsLog.person values from display name to username.

    Old completions stored the person's display name (e.g. 'Derek').
    New completions store the username (e.g. 'derek').
    This runs at startup to bring all entries in line with the username convention.
    Idempotent: safe to run on every startup.
    """
    people_result = await db.execute(select(Person))
    people = people_result.scalars().all()
    for person in people:
        if person.name != person.username:
            await db.execute(
                update(PointsLog)
                .where(PointsLog.person == person.name)
                .values(person=person.username)
            )
    try:
        await db.commit()
    except IntegrityError as e:
        await db.rollback()
        logger.exception("Integrity error normalizing points log persons")
        raise
    except Exception:
        await db.rollback()
        logger.exception("Unexpected error normalizing points log persons")
        raise


def _slugify(name: str) -> str:
    return re.sub(r"[^a-z0-9]+", "_", name.lower()).strip("_")


def _now() -> datetime:
    return datetime.now(timezone.utc)


def get_today(tz_name: str = "UTC") -> date:
    """Get today's date in specified timezone."""
    if tz_name == "UTC":
        return datetime.now(timezone.utc).date()
    try:
        from zoneinfo import ZoneInfo
        tz = ZoneInfo(tz_name)
        return datetime.now(tz).date()
    except (ImportError, Exception):
        # Fallback to UTC if timezone is invalid
        return datetime.now(timezone.utc).date()


def validate_assignment(chore) -> Optional[dict[str, str]]:
    """Validate chore assignment configuration.

    Returns None if valid, dict of field->error message if invalid.
    """
    if isinstance(chore, dict):
        assignment_type = chore.get('assignment_type')
        current_assignee = chore.get('current_assignee')
        assignee = chore.get('assignee')
        eligible_people = chore.get('eligible_people') or []
        next_assignee = chore.get('next_assignee')
    else:
        assignment_type = chore.assignment_type
        current_assignee = chore.current_assignee
        assignee = chore.assignee
        eligible_people = chore.eligible_people or []
        next_assignee = getattr(chore, 'next_assignee', None)

    if assignment_type == "open":
        return None

    errors = {}

    if assignment_type == "fixed":
        if not assignee:
            errors["assignee"] = "Fixed assignment requires an assignee"
        elif current_assignee is not None and current_assignee != assignee:
            errors["current_assignee"] = f"Must be assigned to {assignee} for fixed assignment"

    elif assignment_type == "rotating":
        if not eligible_people:
            errors["eligible_people"] = "Rotating assignment requires at least one eligible person"
        else:
            if current_assignee and current_assignee not in eligible_people:
                errors["current_assignee"] = "Not in eligible people list"
            if next_assignee and next_assignee not in eligible_people:
                errors["next_assignee"] = "Not in eligible people list"

    return errors if errors else None


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
    assignee: Optional[str] = None,
) -> None:
    log = ChoreLog(
        chore_id=chore.id,
        chore_name=chore.name,
        person=person,
        action=action,
        timestamp=_now(),
        reassigned_to=reassigned_to,
        assignee=assignee,
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
    try:
        await db.commit()
        await db.refresh(chore)
    except IntegrityError as e:
        await db.rollback()
        if e.orig and "UniqueViolationError" in type(e.orig).__name__:
            logger.warning("Chore '%s' already exists (unique constraint violation)", chore.name)
            raise HTTPException(status_code=409, detail="Chore with that name already exists")
        logger.exception("Unexpected integrity error initializing chore '%s'", chore.name)
        raise HTTPException(status_code=500, detail="Database error while creating chore")
    except Exception:
        await db.rollback()
        logger.exception("Unexpected error initializing chore '%s'", chore.name)
        raise


async def complete_chore(
    chore: Chore,
    db: AsyncSession,
    completed_by: Optional[str] = None,
) -> Chore:
    # Capture the assignee before any reassignment logic runs
    chore_assignee = chore.current_assignee

    # Zero-point chores are simple task reminders: completing one earns no Credit,
    # so no Points Log entry is written (see CONTEXT.md, "Points Log"). The guard is
    # `points > 0`, not `points is not None` — negative values are rejected upstream
    # by schema validation, and 0 means "nothing to credit".
    if chore.points > 0 and completed_by:
        log = PointsLog(
            person=completed_by,
            points=chore.points,
            chore_id=chore.id,
            completed_at=_now(),
        )
        db.add(log)

        # Update person's total points by username
        person_result = await db.execute(select(Person).where(Person.username == completed_by))
        person = person_result.scalar_one_or_none()
        if person:
            person.points += chore.points
            db.add(person)

    if chore.assignment_type == "rotating" and chore.eligible_people:
        chore.rotation_index = (chore.rotation_index + 1) % len(chore.eligible_people)
        chore.current_assignee = chore.eligible_people[chore.rotation_index]

    if chore.assignment_type == "open" and chore.current_assignee is not None:
        chore.current_assignee = None

    chore.next_due = _calc_next_due(chore)
    chore.state = "complete"
    chore.last_changed_at = _now()
    chore.last_changed_by = completed_by
    chore.last_change_type = CHANGE_COMPLETED
    chore.last_completed_at = _now()
    chore.last_completed_by = completed_by

    await _log_action(chore, CHANGE_COMPLETED, completed_by or "system", db, assignee=chore_assignee)

    db.add(chore)
    try:
        await db.commit()
        await db.refresh(chore)
    except IntegrityError as e:
        await db.rollback()
        if e.orig and "UniqueViolationError" in type(e.orig).__name__:
            logger.warning("Integrity error completing chore id=%s", chore.id)
            raise HTTPException(status_code=409, detail="Conflict completing chore")
        logger.exception("Unexpected integrity error completing chore id=%s", chore.id)
        raise HTTPException(status_code=500, detail="Database error while completing chore")
    except Exception:
        await db.rollback()
        logger.exception("Unexpected error completing chore id=%s", chore.id)
        raise
    return chore


async def skip_chore(chore: Chore, db: AsyncSession, skipped_by: Optional[str] = None) -> Chore:
    chore.next_due = _calc_next_due(chore)
    chore.state = "complete"
    chore.last_changed_at = _now()
    chore.last_changed_by = None
    chore.last_change_type = CHANGE_SKIPPED

    await _log_action(chore, CHANGE_SKIPPED, skipped_by or "system", db)

    db.add(chore)
    try:
        await db.commit()
        await db.refresh(chore)
    except IntegrityError as e:
        await db.rollback()
        if e.orig and "UniqueViolationError" in type(e.orig).__name__:
            logger.warning("Integrity error skipping chore id=%s", chore.id)
            raise HTTPException(status_code=409, detail="Conflict skipping chore")
        logger.exception("Unexpected integrity error skipping chore id=%s", chore.id)
        raise HTTPException(status_code=500, detail="Database error while skipping chore")
    except Exception:
        await db.rollback()
        logger.exception("Unexpected error skipping chore id=%s", chore.id)
        raise
    return chore


async def skip_and_reassign_chore(
    chore: Chore,
    db: AsyncSession,
    assignee: Optional[str] = None,
    skipped_by: Optional[str] = None,
) -> Chore:
    old_assignee = chore.current_assignee
    chore = await skip_chore(chore, db, skipped_by=skipped_by)

    if assignee:
        chore.current_assignee = assignee
        if chore.assignment_type == "rotating" and assignee in chore.eligible_people:
            chore.rotation_index = chore.eligible_people.index(assignee)
    elif chore.assignment_type == "rotating" and chore.eligible_people:
        chore.rotation_index = (chore.rotation_index + 1) % len(chore.eligible_people)
        chore.current_assignee = chore.eligible_people[chore.rotation_index]

    if chore.current_assignee != old_assignee:
        await _log_action(
            chore,
            CHANGE_REASSIGNED,
            skipped_by or "system",
            db,
            reassigned_to=chore.current_assignee,
        )

    db.add(chore)
    try:
        await db.commit()
        await db.refresh(chore)
    except IntegrityError as e:
        await db.rollback()
        if e.orig and "UniqueViolationError" in type(e.orig).__name__:
            logger.warning("Integrity error in skip_and_reassign for chore id=%s", chore.id)
            raise HTTPException(status_code=409, detail="Conflict during skip and reassign")
        logger.exception("Unexpected integrity error in skip_and_reassign for chore id=%s", chore.id)
        raise HTTPException(status_code=500, detail="Database error while skipping and reassigning chore")
    except Exception:
        await db.rollback()
        logger.exception("Unexpected error in skip_and_reassign for chore id=%s", chore.id)
        raise
    return chore


async def reassign_chore(chore: Chore, db: AsyncSession, assignee: str, person: str = "system") -> Chore:
    chore.current_assignee = assignee
    if chore.assignment_type == "rotating" and assignee in chore.eligible_people:
        chore.rotation_index = chore.eligible_people.index(assignee)
    chore.last_changed_at = _now()
    chore.last_changed_by = None
    chore.last_change_type = CHANGE_REASSIGNED

    await _log_action(chore, CHANGE_REASSIGNED, person, db, reassigned_to=assignee)

    db.add(chore)
    try:
        await db.commit()
        await db.refresh(chore)
    except IntegrityError as e:
        await db.rollback()
        if e.orig and "UniqueViolationError" in type(e.orig).__name__:
            logger.warning("Integrity error reassigning chore id=%s", chore.id)
            raise HTTPException(status_code=409, detail="Conflict reassigning chore")
        logger.exception("Unexpected integrity error reassigning chore id=%s", chore.id)
        raise HTTPException(status_code=500, detail="Database error while reassigning chore")
    except Exception:
        await db.rollback()
        logger.exception("Unexpected error reassigning chore id=%s", chore.id)
        raise
    return chore


async def mark_due_chore(chore: Chore, db: AsyncSession, marked_by: Optional[str] = None, timezone: str = None) -> Chore:
    # If timezone not provided, use system local date (for backward compatibility with tests)
    today = get_today(timezone) if timezone else date.today()
    if chore.state == "due" and chore.next_due == today:
        return chore
    chore.state = "due"
    chore.next_due = today
    chore.last_changed_at = _now()
    chore.last_changed_by = marked_by
    chore.last_change_type = CHANGE_MARKED_DUE

    await _log_action(chore, CHANGE_MARKED_DUE, marked_by or "system", db)

    db.add(chore)
    try:
        await db.commit()
        await db.refresh(chore)
    except IntegrityError as e:
        await db.rollback()
        if e.orig and "UniqueViolationError" in type(e.orig).__name__:
            logger.warning("Integrity error marking chore id=%s as due", chore.id)
            raise HTTPException(status_code=409, detail="Conflict marking chore as due")
        logger.exception("Unexpected integrity error marking chore id=%s as due", chore.id)
        raise HTTPException(status_code=500, detail="Database error while marking chore as due")
    except Exception:
        await db.rollback()
        logger.exception("Unexpected error marking chore id=%s as due", chore.id)
        raise
    return chore


def _relevant_usernames(chore: Chore) -> list[str]:
    """Usernames of the people a due Chore should notify.

    - Assigned chore (fixed/rotating) with a current_assignee -> just that person.
    - Open chore (current_assignee is None) -> every username in eligible_people.
    - Open chore with empty eligible_people -> nobody.
    """
    if chore.current_assignee:
        return [chore.current_assignee]
    return list(chore.eligible_people or [])


async def _generate_chore_due_notifications(db: AsyncSession, chores: list[Chore]) -> int:
    """Create one chore_due Notification per relevant person for each transitioned chore.

    Recipients are resolved from usernames to Person.id. A recipient with an
    explicit NotificationPreference(type=chore_due, enabled=False) row is skipped;
    an absent row means enabled. Rows are added to the session but not committed —
    the caller commits in the same transaction as the due transition.
    """
    if not chores:
        return 0

    # Map username -> person id for all people (reference columns store usernames).
    people_result = await db.execute(select(Person))
    username_to_id = {p.username: p.id for p in people_result.scalars().all()}

    # People who have explicitly disabled chore_due notifications.
    pref_result = await db.execute(
        select(NotificationPreference.person_id).where(
            NotificationPreference.type == NOTIFICATION_TYPE_CHORE_DUE,
            NotificationPreference.enabled == False,  # noqa: E712 — SQL boolean comparison
        )
    )
    opted_out_ids = set(pref_result.scalars().all())

    now = _now()
    created = 0
    for chore in chores:
        for username in _relevant_usernames(chore):
            person_id = username_to_id.get(username)
            if person_id is None:
                continue
            if person_id in opted_out_ids:
                continue
            db.add(
                Notification(
                    person_id=person_id,
                    type=NOTIFICATION_TYPE_CHORE_DUE,
                    chore_id=chore.id,
                    title=chore.name,
                    body=f'The chore "{chore.name}" is now due.',
                    created_at=now,
                    delivered_at=None,
                    acknowledged_at=None,
                    dismissed_at=None,
                )
            )
            created += 1
    return created


async def _dismiss_stale_notifications(db: AsyncSession) -> int:
    """Dismiss unacknowledged chore_due notifications whose chore is no longer due.

    Sets dismissed_at on every chore_due Notification where acknowledged_at IS NULL
    and dismissed_at IS NULL and the referenced chore is no longer due (state != "due"
    or the chore no longer exists). Acknowledged rows are never touched. Rows are
    updated on the session but not committed — the caller commits.
    """
    result = await db.execute(
        select(Notification).where(
            Notification.type == NOTIFICATION_TYPE_CHORE_DUE,
            Notification.acknowledged_at.is_(None),
            Notification.dismissed_at.is_(None),
        )
    )
    candidates = result.scalars().all()
    if not candidates:
        return 0

    chore_ids = {n.chore_id for n in candidates if n.chore_id is not None}
    still_due_ids: set[int] = set()
    if chore_ids:
        chore_result = await db.execute(
            select(Chore.id).where(Chore.id.in_(chore_ids), Chore.state == "due")
        )
        still_due_ids = set(chore_result.scalars().all())

    now = _now()
    dismissed = 0
    for notification in candidates:
        if notification.chore_id in still_due_ids:
            continue
        notification.dismissed_at = now
        db.add(notification)
        dismissed += 1
    return dismissed


async def transition_overdue_chores(db: AsyncSession) -> int:
    """Flip complete chores to due when next_due <= today. Returns count changed.

    In the same transaction this also generates chore_due notifications for the
    people relevant to each transitioned chore, and dismisses stale unacknowledged
    chore_due notifications whose chore is no longer due.
    """
    today = date.today()
    result = await db.execute(
        select(Chore).where(Chore.state == "complete", Chore.next_due <= today)
    )
    chores = result.scalars().all()
    for chore in chores:
        chore.state = "due"
        chore.last_changed_at = _now()
        chore.last_change_type = CHANGE_FORCED_DUE
        await _log_action(chore, CHANGE_MARKED_DUE, "schedule", db)
        db.add(chore)

    notifications_created = await _generate_chore_due_notifications(db, chores)
    dismissed = await _dismiss_stale_notifications(db)

    if chores or dismissed:
        try:
            await db.commit()
        except IntegrityError as e:
            await db.rollback()
            if e.orig and "UniqueViolationError" in type(e.orig).__name__:
                logger.warning("Integrity error during overdue chore transition")
                raise
            logger.exception("Unexpected integrity error during overdue chore transition")
            raise
        except Exception:
            await db.rollback()
            logger.exception("Unexpected error during overdue chore transition")
            raise

    if notifications_created:
        logger.info("Generated %d chore_due notification(s)", notifications_created)
    if dismissed:
        logger.info("Dismissed %d stale notification(s)", dismissed)

    return len(chores)
