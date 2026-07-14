"""Tests for notification generation and stale dismissal in the due-transition job.

Generation and stale dismissal are folded into
``transition_overdue_chores`` (app/services/chore_service.py), which the
scheduler's ``_midnight_transition`` and the app-startup lifespan both call.
"""
from datetime import date, datetime, timedelta, timezone

import pytest
from sqlalchemy import select

from app.models import Chore, Notification, NotificationPreference, Person
from app.services.chore_service import (
    NOTIFICATION_TYPE_CHORE_DUE,
    transition_overdue_chores,
)


def _naive(dt: datetime) -> datetime:
    """Drop tzinfo for comparison — SQLite stores DateTime(timezone=True) naive."""
    return dt.replace(tzinfo=None) if dt.tzinfo else dt


def _yesterday() -> date:
    return date.today() - timedelta(days=1)


def _tomorrow() -> date:
    return date.today() + timedelta(days=1)


async def _make_person(db, username: str) -> Person:
    person = Person(name=username.title(), username=username, password_hash="x")
    db.add(person)
    await db.commit()
    await db.refresh(person)
    return person


async def _make_complete_due_chore(db, **kwargs) -> Chore:
    """A chore in state 'complete' whose next_due is in the past (ready to flip)."""
    defaults = dict(
        name="Dishes",
        schedule_type="interval",
        schedule_config={"days": 7},
        assignment_type="open",
        eligible_people=[],
        points=0,
        state="complete",
        next_due=_yesterday(),
        rotation_index=0,
    )
    defaults.update(kwargs)
    chore = Chore(**defaults)
    db.add(chore)
    await db.commit()
    await db.refresh(chore)
    return chore


async def _notifications(db) -> list[Notification]:
    result = await db.execute(select(Notification))
    return list(result.scalars().all())


class TestGeneration:
    @pytest.mark.asyncio
    async def test_fixed_assignee_gets_one_notification(self, db):
        derek = await _make_person(db, "derek")
        chore = await _make_complete_due_chore(
            db, name="Trash", assignment_type="fixed",
            assignee="derek", current_assignee="derek",
        )

        count = await transition_overdue_chores(db)

        assert count == 1
        notes = await _notifications(db)
        assert len(notes) == 1
        n = notes[0]
        assert n.person_id == derek.id
        assert n.type == NOTIFICATION_TYPE_CHORE_DUE
        assert n.chore_id == chore.id
        assert n.title == "Trash"
        assert "Trash" in n.body
        assert n.created_at is not None
        assert n.delivered_at is None
        assert n.acknowledged_at is None
        assert n.dismissed_at is None

    @pytest.mark.asyncio
    async def test_rotating_notifies_current_assignee_only(self, db):
        amy = await _make_person(db, "amy")
        await _make_person(db, "connor")
        await _make_complete_due_chore(
            db, name="Vacuum", assignment_type="rotating",
            eligible_people=["amy", "connor"], current_assignee="amy",
        )

        await transition_overdue_chores(db)

        notes = await _notifications(db)
        assert len(notes) == 1
        assert notes[0].person_id == amy.id

    @pytest.mark.asyncio
    async def test_open_chore_notifies_every_eligible_person(self, db):
        amy = await _make_person(db, "amy")
        connor = await _make_person(db, "connor")
        await _make_complete_due_chore(
            db, name="Lawn", assignment_type="open",
            eligible_people=["amy", "connor"], current_assignee=None,
        )

        await transition_overdue_chores(db)

        notes = await _notifications(db)
        assert {n.person_id for n in notes} == {amy.id, connor.id}
        assert all(n.type == NOTIFICATION_TYPE_CHORE_DUE for n in notes)

    @pytest.mark.asyncio
    async def test_open_chore_with_empty_eligible_people_notifies_nobody(self, db):
        await _make_person(db, "derek")
        await _make_complete_due_chore(
            db, name="Nobody", assignment_type="open",
            eligible_people=[], current_assignee=None,
        )

        count = await transition_overdue_chores(db)

        assert count == 1  # chore still transitions
        assert await _notifications(db) == []

    @pytest.mark.asyncio
    async def test_preference_optout_skips_recipient(self, db):
        amy = await _make_person(db, "amy")
        connor = await _make_person(db, "connor")
        # Amy explicitly disabled chore_due; connor has no row (= enabled).
        db.add(NotificationPreference(
            person_id=amy.id, type=NOTIFICATION_TYPE_CHORE_DUE, enabled=False,
        ))
        await db.commit()
        await _make_complete_due_chore(
            db, name="Sweep", assignment_type="open",
            eligible_people=["amy", "connor"], current_assignee=None,
        )

        await transition_overdue_chores(db)

        notes = await _notifications(db)
        assert [n.person_id for n in notes] == [connor.id]

    @pytest.mark.asyncio
    async def test_preference_enabled_true_row_still_notifies(self, db):
        derek = await _make_person(db, "derek")
        db.add(NotificationPreference(
            person_id=derek.id, type=NOTIFICATION_TYPE_CHORE_DUE, enabled=True,
        ))
        await db.commit()
        await _make_complete_due_chore(
            db, name="Mop", assignment_type="fixed",
            assignee="derek", current_assignee="derek",
        )

        await transition_overdue_chores(db)

        notes = await _notifications(db)
        assert len(notes) == 1 and notes[0].person_id == derek.id

    @pytest.mark.asyncio
    async def test_no_duplicate_on_second_run(self, db):
        await _make_person(db, "derek")
        await _make_complete_due_chore(
            db, name="Trash", assignment_type="fixed",
            assignee="derek", current_assignee="derek",
        )

        await transition_overdue_chores(db)
        # Chore is now "due"; a second run selects only "complete" chores.
        await transition_overdue_chores(db)

        assert len(await _notifications(db)) == 1


class TestStaleDismissal:
    @pytest.mark.asyncio
    async def test_dismisses_notification_when_chore_no_longer_due(self, db):
        derek = await _make_person(db, "derek")
        # A completed chore (not due) with a lingering unacknowledged notification.
        chore = await _make_complete_due_chore(
            db, name="Old", assignment_type="fixed",
            assignee="derek", current_assignee="derek",
            state="complete", next_due=_tomorrow(),
        )
        db.add(Notification(
            person_id=derek.id, type=NOTIFICATION_TYPE_CHORE_DUE, chore_id=chore.id,
            title="Old", body="due", created_at=datetime.now(timezone.utc),
        ))
        await db.commit()

        await transition_overdue_chores(db)

        notes = await _notifications(db)
        assert len(notes) == 1
        assert notes[0].dismissed_at is not None

    @pytest.mark.asyncio
    async def test_keeps_notification_when_chore_still_due(self, db):
        derek = await _make_person(db, "derek")
        chore = await _make_complete_due_chore(
            db, name="StillDue", assignment_type="fixed",
            assignee="derek", current_assignee="derek",
            state="due", next_due=date.today(),
        )
        db.add(Notification(
            person_id=derek.id, type=NOTIFICATION_TYPE_CHORE_DUE, chore_id=chore.id,
            title="StillDue", body="due", created_at=datetime.now(timezone.utc),
        ))
        await db.commit()

        await transition_overdue_chores(db)

        notes = await _notifications(db)
        assert len(notes) == 1
        assert notes[0].dismissed_at is None

    @pytest.mark.asyncio
    async def test_dismisses_when_chore_deleted(self, db):
        derek = await _make_person(db, "derek")
        db.add(Notification(
            person_id=derek.id, type=NOTIFICATION_TYPE_CHORE_DUE, chore_id=99999,
            title="Ghost", body="due", created_at=datetime.now(timezone.utc),
        ))
        await db.commit()

        await transition_overdue_chores(db)

        notes = await _notifications(db)
        assert len(notes) == 1
        assert notes[0].dismissed_at is not None

    @pytest.mark.asyncio
    async def test_never_dismisses_acknowledged_notification(self, db):
        derek = await _make_person(db, "derek")
        # Chore no longer due, but the notification was acknowledged.
        chore = await _make_complete_due_chore(
            db, name="Ack", assignment_type="fixed",
            assignee="derek", current_assignee="derek",
            state="complete", next_due=_tomorrow(),
        )
        acked_at = datetime.now(timezone.utc) - timedelta(hours=1)
        db.add(Notification(
            person_id=derek.id, type=NOTIFICATION_TYPE_CHORE_DUE, chore_id=chore.id,
            title="Ack", body="due", created_at=datetime.now(timezone.utc),
            acknowledged_at=acked_at,
        ))
        await db.commit()

        await transition_overdue_chores(db)

        notes = await _notifications(db)
        assert len(notes) == 1
        assert notes[0].dismissed_at is None
        # SQLite drops tzinfo on read-back; compare wall-clock values.
        assert _naive(notes[0].acknowledged_at) == _naive(acked_at)

    @pytest.mark.asyncio
    async def test_does_not_redismiss_already_dismissed(self, db):
        derek = await _make_person(db, "derek")
        chore = await _make_complete_due_chore(
            db, name="Dis", assignment_type="fixed",
            assignee="derek", current_assignee="derek",
            state="complete", next_due=_tomorrow(),
        )
        original = datetime.now(timezone.utc) - timedelta(days=2)
        db.add(Notification(
            person_id=derek.id, type=NOTIFICATION_TYPE_CHORE_DUE, chore_id=chore.id,
            title="Dis", body="due", created_at=datetime.now(timezone.utc),
            dismissed_at=original,
        ))
        await db.commit()

        await transition_overdue_chores(db)

        notes = await _notifications(db)
        assert len(notes) == 1
        # SQLite drops tzinfo on read-back; compare wall-clock values.
        assert _naive(notes[0].dismissed_at) == _naive(original)  # untouched
