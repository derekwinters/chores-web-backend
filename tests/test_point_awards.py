"""Tests for the one-time admin point award endpoint (POST /v1/points/award).

Covers the happy path, admin-vs-non-admin authorization, validation of the
required reason and non-positive amounts, and the append-only Points Log +
Activity Log (UserLog) audit entries.
"""
import pytest
from httpx import AsyncClient
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models import Person, PointsLog, Settings, UserLog
from app.security import hash_password


async def _setup_users(db: AsyncSession) -> None:
    db.add(Settings(key="auth_enabled", value="true"))
    db.add_all([
        Person(name="Admin", username="admin", password_hash=hash_password("admin_pass"), is_admin=True),
        Person(name="Regular", username="regular", password_hash=hash_password("regular_pass"), is_admin=False),
        Person(name="Recipient", username="recipient", password_hash=hash_password("recipient_pass"), is_admin=False),
    ])
    await db.commit()


async def _token(client: AsyncClient, username: str, password: str) -> str:
    r = await client.post("/v1/auth/login", json={"username": username, "password": password})
    assert r.status_code == 200, r.text
    return r.json()["access_token"]


@pytest.mark.asyncio
async def test_admin_can_award_points_happy_path(client: AsyncClient, db: AsyncSession):
    await _setup_users(db)
    token = await _token(client, "admin", "admin_pass")

    r = await client.post(
        "/v1/points/award",
        json={"person": "recipient", "points": 10, "reason": "Helping with gardening"},
        headers={"Authorization": f"Bearer {token}"},
    )
    assert r.status_code == 201, r.text
    body = r.json()
    assert body["person"] == "recipient"
    assert body["points"] == 10

    # Append-only Points Log entry (a Credit) exists, not tied to a real chore.
    logs = (await db.execute(select(PointsLog).where(PointsLog.person == "recipient"))).scalars().all()
    assert len(logs) == 1
    assert logs[0].points == 10
    assert logs[0].chore_id == 0


@pytest.mark.asyncio
async def test_award_writes_activity_log_entry(client: AsyncClient, db: AsyncSession):
    await _setup_users(db)
    token = await _token(client, "admin", "admin_pass")

    r = await client.post(
        "/v1/points/award",
        json={"person": "recipient", "points": 5, "reason": "Extra effort"},
        headers={"Authorization": f"Bearer {token}"},
    )
    assert r.status_code == 201, r.text

    entries = (await db.execute(select(UserLog).where(UserLog.action == "points_awarded"))).scalars().all()
    assert len(entries) == 1
    entry = entries[0]
    assert entry.person_name == "Recipient"   # to whom
    assert entry.changed_by == "admin"          # who granted
    assert entry.new_value == "5"               # amount
    assert entry.old_value == "Extra effort"    # reason


@pytest.mark.asyncio
async def test_award_appears_in_activity_log_endpoint(client: AsyncClient, db: AsyncSession):
    await _setup_users(db)
    token = await _token(client, "admin", "admin_pass")

    await client.post(
        "/v1/points/award",
        json={"person": "recipient", "points": 7, "reason": "Helped a neighbour"},
        headers={"Authorization": f"Bearer {token}"},
    )

    r = await client.get("/v1/log", headers={"Authorization": f"Bearer {token}"})
    assert r.status_code == 200, r.text
    awarded = [e for e in r.json() if e["action"] == "points_awarded"]
    assert len(awarded) == 1


@pytest.mark.asyncio
async def test_non_admin_cannot_award_points(client: AsyncClient, db: AsyncSession):
    await _setup_users(db)
    token = await _token(client, "regular", "regular_pass")

    r = await client.post(
        "/v1/points/award",
        json={"person": "recipient", "points": 10, "reason": "Helping with gardening"},
        headers={"Authorization": f"Bearer {token}"},
    )
    assert r.status_code == 403

    # No Credit written on a rejected request.
    logs = (await db.execute(select(PointsLog))).scalars().all()
    assert logs == []


@pytest.mark.asyncio
async def test_award_requires_authentication(client: AsyncClient, db: AsyncSession):
    await _setup_users(db)
    r = await client.post(
        "/v1/points/award",
        json={"person": "recipient", "points": 10, "reason": "Helping with gardening"},
    )
    assert r.status_code == 401


@pytest.mark.asyncio
async def test_award_rejects_missing_reason(client: AsyncClient, db: AsyncSession):
    await _setup_users(db)
    token = await _token(client, "admin", "admin_pass")

    r = await client.post(
        "/v1/points/award",
        json={"person": "recipient", "points": 10},
        headers={"Authorization": f"Bearer {token}"},
    )
    assert r.status_code == 422


@pytest.mark.asyncio
async def test_award_rejects_blank_reason(client: AsyncClient, db: AsyncSession):
    await _setup_users(db)
    token = await _token(client, "admin", "admin_pass")

    r = await client.post(
        "/v1/points/award",
        json={"person": "recipient", "points": 10, "reason": "   "},
        headers={"Authorization": f"Bearer {token}"},
    )
    assert r.status_code == 422


@pytest.mark.asyncio
@pytest.mark.parametrize("amount", [0, -5])
async def test_award_rejects_non_positive_amount(client: AsyncClient, db: AsyncSession, amount: int):
    await _setup_users(db)
    token = await _token(client, "admin", "admin_pass")

    r = await client.post(
        "/v1/points/award",
        json={"person": "recipient", "points": amount, "reason": "Helping with gardening"},
        headers={"Authorization": f"Bearer {token}"},
    )
    assert r.status_code == 422


@pytest.mark.asyncio
async def test_award_unknown_person_returns_404(client: AsyncClient, db: AsyncSession):
    await _setup_users(db)
    token = await _token(client, "admin", "admin_pass")

    r = await client.post(
        "/v1/points/award",
        json={"person": "ghost", "points": 10, "reason": "Helping with gardening"},
        headers={"Authorization": f"Bearer {token}"},
    )
    assert r.status_code == 404
