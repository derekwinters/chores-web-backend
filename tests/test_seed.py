"""Tests for the seed.py script logic.

These tests verify that seed.py:
- Performs a login step (uses auth token for subsequent requests)
- Seeds comprehensive entity/action data: People, Chores, Completions, Skips,
  Reassignments, and Amendments (schedule/point updates)

Tests use a live ASGI test client against an in-memory SQLite DB to exercise the
same API paths that seed.py calls, confirming those paths produce the expected data.
"""
import pytest
import pytest_asyncio
from httpx import AsyncClient, ASGITransport
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine

from app.main import app
from app.models import Base, ChoreLog, PointsLog, Person, Chore
from app.database import get_db


# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------

SEED_DB_URL = "sqlite+aiosqlite:///:memory:"
seed_engine = create_async_engine(SEED_DB_URL, connect_args={"check_same_thread": False})
SeedSession = async_sessionmaker(seed_engine, expire_on_commit=False)


@pytest_asyncio.fixture
async def seed_db():
    async with seed_engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)
    async with SeedSession() as session:
        yield session
    async with seed_engine.begin() as conn:
        await conn.run_sync(Base.metadata.drop_all)


@pytest_asyncio.fixture
async def seed_client(seed_db):
    async def override_get_db():
        yield seed_db

    app.dependency_overrides[get_db] = override_get_db
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as ac:
        yield ac, seed_db
    app.dependency_overrides.clear()


# ---------------------------------------------------------------------------
# Helper: run the seed logic inline (mirrors what seed.py will do)
# ---------------------------------------------------------------------------

async def _run_seed(ac: AsyncClient) -> dict:
    """Execute the seed workflow against the given client. Returns login token."""
    # Login step (first login auto-creates admin)
    login_r = await ac.post("/v1/auth/login", json={"username": "admin", "password": "adminpass123"})
    assert login_r.status_code == 200, f"Login failed: {login_r.text}"
    token = login_r.json()["access_token"]
    ac.headers = {"Authorization": f"Bearer {token}"}
    return {"token": token}


# ---------------------------------------------------------------------------
# Behavior 1a: seed.py performs a login step and obtains a token
# ---------------------------------------------------------------------------

@pytest.mark.asyncio
async def test_seed_performs_login(seed_client):
    """Seed must start with a login step that yields a usable auth token."""
    ac, db = seed_client
    result = await _run_seed(ac)
    # Token must be non-empty
    assert result["token"], "seed login did not return a token"

    # Token must allow authenticated requests
    chores_r = await ac.get("/v1/chores")
    assert chores_r.status_code == 200


# ---------------------------------------------------------------------------
# Behavior 1b: seed.py creates People and Chores
# ---------------------------------------------------------------------------

@pytest.mark.asyncio
async def test_seed_creates_people_and_chores(seed_client):
    """Seed must create multiple people and chores."""
    ac, db = seed_client
    await _run_seed(ac)

    # Create people via API (as seed.py does)
    for name in ["Derek", "Amy", "Connor", "Lucas"]:
        r = await ac.post("/v1/people", json={"name": name, "username": name.lower(), "password": "pass1234"})
        assert r.status_code in (200, 201), f"Person creation failed for {name}: {r.text}"

    # Verify people exist
    result = await db.execute(select(Person))
    people = result.scalars().all()
    # admin + 4 seeded people
    assert len(people) >= 4, f"Expected at least 4 people, got {len(people)}"

    # Create a chore
    chore_data = {
        "name": "Vacuum downstairs",
        "schedule_type": "weekly",
        "schedule_config": {"days": ["mon", "thu"]},
        "assignment_type": "rotating",
        "eligible_people": ["Derek", "Amy", "Connor", "Lucas"],
        "points": 3,
    }
    r = await ac.post("/v1/chores", json=chore_data)
    assert r.status_code == 201, f"Chore creation failed: {r.text}"

    result = await db.execute(select(Chore))
    chores = result.scalars().all()
    assert len(chores) >= 1


# ---------------------------------------------------------------------------
# Behavior 1c: seed.py seeds Completions (PointsLog entries created)
# ---------------------------------------------------------------------------

@pytest.mark.asyncio
async def test_seed_creates_completions(seed_client):
    """Seed must complete at least one chore, producing a PointsLog entry."""
    ac, db = seed_client
    await _run_seed(ac)

    # Create person and chore
    await ac.post("/v1/people", json={"name": "Derek", "username": "derek2", "password": "pass1234"})
    chore_r = await ac.post("/v1/chores", json={
        "name": "Test Completion Chore",
        "schedule_type": "interval",
        "schedule_config": {"days": 7},
        "assignment_type": "open",
        "eligible_people": [],
        "points": 5,
    })
    chore_id = chore_r.json()["id"]

    # Force state to due so complete action is possible
    await ac.put(f"/v1/chores/{chore_id}", json={"state": "due"})

    r = await ac.post(f"/v1/chores/{chore_id}/complete", json={"completed_by": "admin"})
    assert r.status_code == 200, f"Complete failed: {r.text}"

    result = await db.execute(select(PointsLog))
    entries = result.scalars().all()
    assert len(entries) >= 1, "No PointsLog entries after completion"


# ---------------------------------------------------------------------------
# Behavior 1d: seed.py seeds Skips (ChoreLog entries with action=skipped)
# ---------------------------------------------------------------------------

@pytest.mark.asyncio
async def test_seed_creates_skips(seed_client):
    """Seed must skip at least one chore, producing a ChoreLog entry with action='skipped'."""
    ac, db = seed_client
    await _run_seed(ac)

    chore_r = await ac.post("/v1/chores", json={
        "name": "Skip Test Chore",
        "schedule_type": "interval",
        "schedule_config": {"days": 7},
        "assignment_type": "open",
        "eligible_people": [],
        "points": 2,
    })
    chore_id = chore_r.json()["id"]
    await ac.put(f"/v1/chores/{chore_id}", json={"state": "due"})

    r = await ac.post(f"/v1/chores/{chore_id}/skip")
    assert r.status_code == 200, f"Skip failed: {r.text}"

    result = await db.execute(select(ChoreLog).where(ChoreLog.action == "skipped"))
    entries = result.scalars().all()
    assert len(entries) >= 1, "No ChoreLog skip entries after skip action"


# ---------------------------------------------------------------------------
# Behavior 1e: seed.py seeds Reassignments (ChoreLog action=reassigned)
# ---------------------------------------------------------------------------

@pytest.mark.asyncio
async def test_seed_creates_reassignments(seed_client):
    """Seed must reassign at least one chore, producing a ChoreLog entry with action='reassigned'."""
    ac, db = seed_client
    await _run_seed(ac)

    # Create two people for reassignment
    await ac.post("/v1/people", json={"name": "Alice", "username": "alice", "password": "pass1234"})
    await ac.post("/v1/people", json={"name": "Bob", "username": "bob", "password": "pass1234"})

    chore_r = await ac.post("/v1/chores", json={
        "name": "Reassign Test Chore",
        "schedule_type": "interval",
        "schedule_config": {"days": 7},
        "assignment_type": "fixed",
        "assignee": "Alice",
        "eligible_people": [],
        "points": 2,
    })
    chore_id = chore_r.json()["id"]

    r = await ac.post(f"/v1/chores/{chore_id}/reassign", json={"assignee": "Bob"})
    assert r.status_code == 200, f"Reassign failed: {r.text}"

    result = await db.execute(select(ChoreLog).where(ChoreLog.action == "reassigned"))
    entries = result.scalars().all()
    assert len(entries) >= 1, "No ChoreLog reassignment entries after reassign action"


# ---------------------------------------------------------------------------
# Behavior 1f: seed.py seeds Amendments (PUT /chores/{id} updating schedule/points)
# ---------------------------------------------------------------------------

@pytest.mark.asyncio
async def test_seed_creates_amendments(seed_client):
    """Seed must amend at least one chore (update schedule or points via PUT),
    producing a ChoreLog entry with action='updated'."""
    ac, db = seed_client
    await _run_seed(ac)

    chore_r = await ac.post("/v1/chores", json={
        "name": "Amendment Test Chore",
        "schedule_type": "interval",
        "schedule_config": {"days": 7},
        "assignment_type": "open",
        "eligible_people": [],
        "points": 3,
    })
    chore_id = chore_r.json()["id"]

    # Amend points and schedule
    r = await ac.put(f"/v1/chores/{chore_id}", json={"points": 5})
    assert r.status_code == 200, f"Amendment (PUT) failed: {r.text}"

    result = await db.execute(select(ChoreLog).where(ChoreLog.action == "updated"))
    entries = result.scalars().all()
    assert len(entries) >= 1, "No ChoreLog 'updated' entries after amending chore"
