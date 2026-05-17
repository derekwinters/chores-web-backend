"""Tests for points_log person normalization and stats endpoint with username routing."""
import pytest
from datetime import datetime, timezone
from httpx import AsyncClient
from sqlalchemy.ext.asyncio import AsyncSession

from app.models import Person, PointsLog, Settings
from app.security import hash_password


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

async def _make_person(db: AsyncSession, name: str, username: str, points: int = 0) -> Person:
    person = Person(
        name=name,
        username=username,
        password_hash=hash_password("pass"),
        is_admin=False,
        points=points,
    )
    db.add(person)
    await db.commit()
    await db.refresh(person)
    return person


async def _make_admin(db: AsyncSession) -> Person:
    db.add(Settings(key="auth_enabled", value="true"))
    person = Person(
        name="Admin",
        username="admin",
        password_hash=hash_password("adminpass"),
        is_admin=True,
        points=0,
    )
    db.add(person)
    await db.commit()
    await db.refresh(person)
    return person


async def _make_points_log(db: AsyncSession, person_name: str, points: int) -> PointsLog:
    row = PointsLog(
        person=person_name,
        points=points,
        chore_id=1,
        completed_at=datetime.now(timezone.utc),
    )
    db.add(row)
    await db.commit()
    await db.refresh(row)
    return row


async def _token(client: AsyncClient, username: str = "admin", password: str = "adminpass") -> str:
    r = await client.post("/auth/login", json={"username": username, "password": password})
    return r.json()["access_token"]


# ---------------------------------------------------------------------------
# Tests: normalize_points_log_persons
# ---------------------------------------------------------------------------

class TestNormalizePointsLogPersons:
    @pytest.mark.asyncio
    async def test_normalizes_display_name_to_username(self, db: AsyncSession):
        """Legacy entries storing display name are updated to username."""
        from app.services.chore_service import normalize_points_log_persons

        person = await _make_person(db, name="Derek", username="derek")
        # Legacy entry: person stored as display name
        row = await _make_points_log(db, person_name="Derek", points=5)

        await normalize_points_log_persons(db)

        await db.refresh(row)
        assert row.person == "derek"  # normalized to username

    @pytest.mark.asyncio
    async def test_skips_already_normalized_entries(self, db: AsyncSession):
        """Entries already using username are untouched."""
        from app.services.chore_service import normalize_points_log_persons

        person = await _make_person(db, name="Derek", username="derek")
        row = await _make_points_log(db, person_name="derek", points=5)

        await normalize_points_log_persons(db)

        await db.refresh(row)
        assert row.person == "derek"

    @pytest.mark.asyncio
    async def test_normalizes_multiple_people(self, db: AsyncSession):
        """All people with display-name entries get normalized."""
        from app.services.chore_service import normalize_points_log_persons

        await _make_person(db, name="Derek", username="derek")
        await _make_person(db, name="Amy", username="amy")
        row1 = await _make_points_log(db, person_name="Derek", points=3)
        row2 = await _make_points_log(db, person_name="Amy", points=2)
        row3 = await _make_points_log(db, person_name="amy", points=1)  # already normalized

        await normalize_points_log_persons(db)

        await db.refresh(row1)
        await db.refresh(row2)
        await db.refresh(row3)
        assert row1.person == "derek"
        assert row2.person == "amy"
        assert row3.person == "amy"  # unchanged


# ---------------------------------------------------------------------------
# Tests: /points/stats/{username} returns combined totals
# ---------------------------------------------------------------------------

class TestStatsEndpointByUsername:
    @pytest.mark.asyncio
    async def test_stats_returns_total_for_username(self, client: AsyncClient, db: AsyncSession):
        """Stats endpoint called with username returns correct total."""
        await _make_admin(db)
        await _make_person(db, name="Derek", username="derek")
        await _make_points_log(db, person_name="derek", points=5)
        await _make_points_log(db, person_name="derek", points=3)

        token = await _token(client)
        r = await client.get("/points/stats/derek", headers={"Authorization": f"Bearer {token}"})

        assert r.status_code == 200
        data = r.json()
        assert data["total_points"] == 8
        assert data["name"] == "Derek"  # display name in response
