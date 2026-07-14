"""Tests for the notifications API router (app/routers/notifications.py):
list with server-owned delivery marking, acknowledge, and preferences.

Uses the ``seeded_client`` fixture (derek logged in; derek/amy/connor/lucas
seeded with auth enabled).
"""
from datetime import datetime, timedelta, timezone

import pytest
import pytest_asyncio
from httpx import AsyncClient, ASGITransport
from sqlalchemy import select

from app.main import app
from app.database import get_db
from app.models import Notification, NotificationPreference, Person
from app.services.chore_service import NOTIFICATION_TYPE_CHORE_DUE


async def _person(db, username: str) -> Person:
    result = await db.execute(select(Person).where(Person.username == username))
    return result.scalar_one()


async def _add_notification(db, person_id: int, **kwargs) -> Notification:
    defaults = dict(
        person_id=person_id,
        type=NOTIFICATION_TYPE_CHORE_DUE,
        chore_id=None,
        title="Chore due",
        body="A chore is due",
        created_at=datetime.now(timezone.utc),
    )
    defaults.update(kwargs)
    notification = Notification(**defaults)
    db.add(notification)
    await db.commit()
    await db.refresh(notification)
    return notification


# ── List: scoping, ordering, filters ─────────────────────────────────────────

class TestList:
    @pytest.mark.asyncio
    async def test_returns_only_callers_notifications(self, seeded_client):
        ac, db = seeded_client
        derek = await _person(db, "derek")
        amy = await _person(db, "amy")
        mine = await _add_notification(db, derek.id, title="Mine")
        await _add_notification(db, amy.id, title="Amys")

        r = await ac.get("/v1/notifications")

        assert r.status_code == 200
        ids = [n["id"] for n in r.json()]
        assert ids == [mine.id]

    @pytest.mark.asyncio
    async def test_newest_first(self, seeded_client):
        ac, db = seeded_client
        derek = await _person(db, "derek")
        now = datetime.now(timezone.utc)
        older = await _add_notification(db, derek.id, created_at=now - timedelta(days=2))
        newer = await _add_notification(db, derek.id, created_at=now - timedelta(hours=1))

        r = await ac.get("/v1/notifications")

        ids = [n["id"] for n in r.json()]
        assert ids == [newer.id, older.id]

    @pytest.mark.asyncio
    async def test_since_filters_by_created_at(self, seeded_client):
        ac, db = seeded_client
        derek = await _person(db, "derek")
        now = datetime.now(timezone.utc)
        await _add_notification(db, derek.id, created_at=now - timedelta(days=10), title="Old")
        recent = await _add_notification(db, derek.id, created_at=now - timedelta(days=1), title="Recent")

        since = (now - timedelta(days=5)).isoformat()
        r = await ac.get("/v1/notifications", params={"since": since})

        titles = [n["title"] for n in r.json()]
        assert titles == ["Recent"]
        assert r.json()[0]["id"] == recent.id

    @pytest.mark.asyncio
    async def test_dismissed_excluded_by_default(self, seeded_client):
        ac, db = seeded_client
        derek = await _person(db, "derek")
        now = datetime.now(timezone.utc)
        # Delivered then dismissed — a seen item retained in the log.
        await _add_notification(
            db, derek.id, title="Dismissed",
            delivered_at=now - timedelta(hours=2), dismissed_at=now - timedelta(hours=1),
        )
        live = await _add_notification(db, derek.id, title="Live")

        r = await ac.get("/v1/notifications")

        assert [n["id"] for n in r.json()] == [live.id]

    @pytest.mark.asyncio
    async def test_dismissed_included_when_requested(self, seeded_client):
        ac, db = seeded_client
        derek = await _person(db, "derek")
        now = datetime.now(timezone.utc)
        dismissed = await _add_notification(
            db, derek.id, title="Dismissed", created_at=now - timedelta(hours=3),
            delivered_at=now - timedelta(hours=2), dismissed_at=now - timedelta(hours=1),
        )
        live = await _add_notification(db, derek.id, title="Live", created_at=now - timedelta(hours=1))

        r = await ac.get("/v1/notifications", params={"include_dismissed": "true"})

        ids = {n["id"] for n in r.json()}
        assert ids == {dismissed.id, live.id}

    @pytest.mark.asyncio
    async def test_pre_dismissed_never_returned(self, seeded_client):
        ac, db = seeded_client
        derek = await _person(db, "derek")
        # Pre-dismissed: dismissed_at set, delivered_at null → never delivered.
        await _add_notification(
            db, derek.id, title="PreDismissed",
            delivered_at=None, dismissed_at=datetime.now(timezone.utc),
        )

        default_r = await ac.get("/v1/notifications")
        included_r = await ac.get("/v1/notifications", params={"include_dismissed": "true"})

        assert default_r.json() == []
        assert included_r.json() == []


# ── Delivery marking (server owns delivery state) ─────────────────────────────

class TestDeliveryMarking:
    @pytest.mark.asyncio
    async def test_first_list_sets_delivered_at_second_preserves_it(self, seeded_client):
        ac, db = seeded_client
        derek = await _person(db, "derek")
        n = await _add_notification(db, derek.id)
        assert n.delivered_at is None

        first = await ac.get("/v1/notifications")
        delivered_at = first.json()[0]["delivered_at"]
        assert delivered_at is not None

        second = await ac.get("/v1/notifications")
        assert second.json()[0]["delivered_at"] == delivered_at

    @pytest.mark.asyncio
    async def test_already_delivered_row_keeps_original(self, seeded_client):
        ac, db = seeded_client
        derek = await _person(db, "derek")
        original = datetime.now(timezone.utc) - timedelta(days=1)
        await _add_notification(db, derek.id, delivered_at=original)

        r = await ac.get("/v1/notifications")
        returned = datetime.fromisoformat(r.json()[0]["delivered_at"])
        # SQLite drops tzinfo on read-back; compare wall-clock values.
        assert returned.replace(tzinfo=None) == original.replace(tzinfo=None)


# ── Acknowledge ───────────────────────────────────────────────────────────────

class TestAck:
    @pytest.mark.asyncio
    async def test_ack_sets_acknowledged_at_and_returns_notification(self, seeded_client):
        ac, db = seeded_client
        derek = await _person(db, "derek")
        n = await _add_notification(db, derek.id)

        r = await ac.post(f"/v1/notifications/{n.id}/ack")

        assert r.status_code == 200
        assert r.json()["id"] == n.id
        assert r.json()["acknowledged_at"] is not None

    @pytest.mark.asyncio
    async def test_ack_is_idempotent(self, seeded_client):
        ac, db = seeded_client
        derek = await _person(db, "derek")
        n = await _add_notification(db, derek.id)

        first = await ac.post(f"/v1/notifications/{n.id}/ack")
        second = await ac.post(f"/v1/notifications/{n.id}/ack")

        assert second.status_code == 200
        assert second.json()["acknowledged_at"] == first.json()["acknowledged_at"]

    @pytest.mark.asyncio
    async def test_ack_nonexistent_returns_404(self, seeded_client):
        ac, _ = seeded_client
        r = await ac.post("/v1/notifications/999999/ack")
        assert r.status_code == 404

    @pytest.mark.asyncio
    async def test_ack_other_persons_notification_returns_404(self, seeded_client):
        ac, db = seeded_client
        amy = await _person(db, "amy")
        n = await _add_notification(db, amy.id, title="Amys")

        r = await ac.post(f"/v1/notifications/{n.id}/ack")

        assert r.status_code == 404
        # Not acknowledged — ownership check happened before any write.
        await db.refresh(n)
        assert n.acknowledged_at is None


# ── Preferences ───────────────────────────────────────────────────────────────

class TestPreferences:
    @pytest.mark.asyncio
    async def test_defaults_absent_row_is_enabled(self, seeded_client):
        ac, _ = seeded_client
        r = await ac.get("/v1/notifications/preferences")
        assert r.status_code == 200
        assert r.json() == {NOTIFICATION_TYPE_CHORE_DUE: True}

    @pytest.mark.asyncio
    async def test_preferences_route_not_captured_by_id(self, seeded_client):
        # A GET to /preferences must hit the map endpoint, never the {id} route
        # (which is POST-only anyway) — a 200 map proves correct ordering.
        ac, _ = seeded_client
        r = await ac.get("/v1/notifications/preferences")
        assert r.status_code == 200
        assert isinstance(r.json(), dict)

    @pytest.mark.asyncio
    async def test_put_upserts_and_round_trips(self, seeded_client):
        ac, db = seeded_client

        put_r = await ac.put(
            "/v1/notifications/preferences",
            json={NOTIFICATION_TYPE_CHORE_DUE: False},
        )
        assert put_r.status_code == 200
        assert put_r.json() == {NOTIFICATION_TYPE_CHORE_DUE: False}

        get_r = await ac.get("/v1/notifications/preferences")
        assert get_r.json() == {NOTIFICATION_TYPE_CHORE_DUE: False}

        # A row was persisted for the caller.
        derek = await _person(db, "derek")
        result = await db.execute(
            select(NotificationPreference).where(
                NotificationPreference.person_id == derek.id
            )
        )
        rows = result.scalars().all()
        assert len(rows) == 1
        assert rows[0].type == NOTIFICATION_TYPE_CHORE_DUE
        assert rows[0].enabled is False

    @pytest.mark.asyncio
    async def test_put_updates_existing_row(self, seeded_client):
        ac, db = seeded_client
        derek = await _person(db, "derek")
        db.add(NotificationPreference(
            person_id=derek.id, type=NOTIFICATION_TYPE_CHORE_DUE, enabled=False,
        ))
        await db.commit()

        put_r = await ac.put(
            "/v1/notifications/preferences",
            json={NOTIFICATION_TYPE_CHORE_DUE: True},
        )

        assert put_r.json() == {NOTIFICATION_TYPE_CHORE_DUE: True}
        result = await db.execute(
            select(NotificationPreference).where(
                NotificationPreference.person_id == derek.id
            )
        )
        rows = result.scalars().all()
        assert len(rows) == 1 and rows[0].enabled is True


# ── Auth ──────────────────────────────────────────────────────────────────────

class TestAuth:
    @pytest_asyncio.fixture
    async def unauth_client(self, seeded_db):
        async def override_get_db():
            yield seeded_db

        app.dependency_overrides[get_db] = override_get_db
        async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as ac:
            yield ac
        app.dependency_overrides.clear()

    @pytest.mark.asyncio
    async def test_list_requires_auth(self, unauth_client):
        r = await unauth_client.get("/v1/notifications")
        assert r.status_code == 401

    @pytest.mark.asyncio
    async def test_ack_requires_auth(self, unauth_client):
        r = await unauth_client.post("/v1/notifications/1/ack")
        assert r.status_code == 401

    @pytest.mark.asyncio
    async def test_preferences_requires_auth(self, unauth_client):
        r = await unauth_client.get("/v1/notifications/preferences")
        assert r.status_code == 401
