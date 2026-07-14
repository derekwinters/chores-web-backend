"""Notifications API — list (with server-owned delivery marking), acknowledge,
and per-type preferences.

Follows the router idiom in ``app/routers/points.py``: auth via
``get_current_user`` (which yields a username string), the caller resolved to a
``Person`` via ``Person.username``, and every query scoped to that person's
``id``. The ``/preferences`` routes are declared BEFORE the ``/{id}`` route so
FastAPI does not match ``preferences`` as an ``{id}`` path parameter.
"""
from datetime import datetime, timezone
from typing import Optional

from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from ..database import get_db
from ..dependencies import get_current_user
from ..models import Notification, NotificationPreference, Person
from ..schemas import (
    NotificationOut,
    NotificationPreferencesOut,
    NotificationPreferencesUpdate,
)
from ..services.chore_service import NOTIFICATION_TYPE_CHORE_DUE

router = APIRouter(prefix="/notifications", tags=["notifications"])

# The set of notification types the preferences map always reports on. v1 has
# exactly one server-generated type; absent = enabled for every type here.
KNOWN_NOTIFICATION_TYPES: tuple[str, ...] = (NOTIFICATION_TYPE_CHORE_DUE,)


async def _resolve_person(current_user: str, db: AsyncSession) -> Person:
    """Resolve the authenticated username to its Person row (404 if unknown)."""
    result = await db.execute(select(Person).where(Person.username == current_user))
    person = result.scalar_one_or_none()
    if person is None:
        raise HTTPException(status_code=404, detail="Person not found")
    return person


# ── Preferences (declared before /{id} so "preferences" isn't captured) ───────

@router.get("/preferences", response_model=NotificationPreferencesOut)
async def get_preferences(
    current_user: str = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """Return the caller's per-type enablement map.

    Every known type is present; a type with no stored row is ``true``
    (absent = enabled).
    """
    person = await _resolve_person(current_user, db)
    result = await db.execute(
        select(NotificationPreference).where(
            NotificationPreference.person_id == person.id
        )
    )
    stored = {row.type: row.enabled for row in result.scalars().all()}
    return {t: stored.get(t, True) for t in KNOWN_NOTIFICATION_TYPES}


@router.put("/preferences", response_model=NotificationPreferencesOut)
async def update_preferences(
    body: NotificationPreferencesUpdate,
    current_user: str = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """Upsert the caller's preference rows and return the resulting map.

    Keys naming unknown types are ignored; the returned map always covers
    every known type.
    """
    person = await _resolve_person(current_user, db)

    result = await db.execute(
        select(NotificationPreference).where(
            NotificationPreference.person_id == person.id
        )
    )
    existing = {row.type: row for row in result.scalars().all()}

    for ntype, enabled in body.root.items():
        if ntype not in KNOWN_NOTIFICATION_TYPES:
            continue
        row = existing.get(ntype)
        if row is None:
            db.add(
                NotificationPreference(
                    person_id=person.id, type=ntype, enabled=enabled
                )
            )
        else:
            row.enabled = enabled
    await db.commit()

    result = await db.execute(
        select(NotificationPreference).where(
            NotificationPreference.person_id == person.id
        )
    )
    stored = {row.type: row.enabled for row in result.scalars().all()}
    return {t: stored.get(t, True) for t in KNOWN_NOTIFICATION_TYPES}


# ── List (with server-owned delivery marking) ─────────────────────────────────

@router.get("", response_model=list[NotificationOut])
async def list_notifications(
    since: Optional[datetime] = Query(
        None, description="Only notifications created strictly after this time."
    ),
    include_dismissed: bool = Query(
        False,
        description=(
            "Include dismissed (but delivered) rows too. Pre-dismissed rows "
            "(dismissed before delivery) are never returned in either mode."
        ),
    ),
    current_user: str = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """Return the caller's notifications, newest first.

    Marks delivery: the first time a notification is returned, its
    ``delivered_at`` is set to now and committed in the same request. Already
    delivered rows keep their original ``delivered_at``.
    """
    person = await _resolve_person(current_user, db)

    query = select(Notification).where(Notification.person_id == person.id)
    if since is not None:
        query = query.where(Notification.created_at > since)

    if include_dismissed:
        # Include dismissed rows, but never pre-dismissed ones (dismissed
        # before delivery): exclude rows that are dismissed AND never delivered.
        query = query.where(
            (Notification.dismissed_at.is_(None))
            | (Notification.delivered_at.is_not(None))
        )
    else:
        query = query.where(Notification.dismissed_at.is_(None))

    query = query.order_by(
        Notification.created_at.desc(), Notification.id.desc()
    )

    result = await db.execute(query)
    notifications = list(result.scalars().all())

    now = datetime.now(timezone.utc)
    newly_delivered = False
    for notification in notifications:
        if notification.delivered_at is None:
            notification.delivered_at = now
            newly_delivered = True
    if newly_delivered:
        await db.commit()

    return notifications


# ── Acknowledge (parameterized route declared last) ───────────────────────────

@router.post("/{id}/ack", response_model=NotificationOut)
async def acknowledge_notification(
    id: int,
    current_user: str = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """Acknowledge the caller's notification and return it.

    Idempotent: an already-acknowledged notification keeps its original
    ``acknowledged_at``. Returns 404 both when the notification does not exist
    and when it belongs to another person (existence is never leaked via 403).
    """
    person = await _resolve_person(current_user, db)

    result = await db.execute(
        select(Notification).where(
            Notification.id == id, Notification.person_id == person.id
        )
    )
    notification = result.scalar_one_or_none()
    if notification is None:
        raise HTTPException(status_code=404, detail="Notification not found")

    if notification.acknowledged_at is None:
        notification.acknowledged_at = datetime.now(timezone.utc)
        await db.commit()

    return notification
