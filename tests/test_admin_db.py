"""Tests for admin_db router: CRUD, access control, audit logging, edge cases."""
import pytest
from datetime import datetime, timezone
from httpx import AsyncClient
from sqlalchemy.ext.asyncio import AsyncSession

from app.models import ChoreLog, Person, PointsLog, Settings
from app.security import hash_password


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

async def _make_admin(db: AsyncSession, username: str = "admin", password: str = "adminpass") -> Person:
    db.add(Settings(key="auth_enabled", value="true"))
    person = Person(
        name="Admin",
        username=username,
        password_hash=hash_password(password),
        is_admin=True,
        points=0,
    )
    db.add(person)
    await db.commit()
    await db.refresh(person)
    return person


async def _make_normal_user(db: AsyncSession, username: str = "user", password: str = "userpass") -> Person:
    person = Person(
        name="User",
        username=username,
        password_hash=hash_password(password),
        is_admin=False,
        points=0,
    )
    db.add(person)
    await db.commit()
    await db.refresh(person)
    return person


async def _make_points_log(
    db: AsyncSession,
    person_name: str = "alice",
    points: int = 10,
    chore_id: int = 1,
) -> PointsLog:
    row = PointsLog(
        person=person_name,
        points=points,
        chore_id=chore_id,
        completed_at=datetime.now(timezone.utc),
    )
    db.add(row)
    await db.commit()
    await db.refresh(row)
    return row


async def _token(client: AsyncClient, username: str, password: str) -> str:
    r = await client.post("/auth/login", json={"username": username, "password": password})
    return r.json()["access_token"]


# ---------------------------------------------------------------------------
# Tests: list (GET)
# ---------------------------------------------------------------------------

class TestListPointsLog:
    @pytest.mark.asyncio
    async def test_admin_can_list(self, client: AsyncClient, db: AsyncSession):
        await _make_admin(db)
        await _make_points_log(db, person_name="Alice", points=5)
        await _make_points_log(db, person_name="Bob", points=8)

        token = await _token(client, "admin", "adminpass")
        r = await client.get("/admin/db/points-log", headers={"Authorization": f"Bearer {token}"})

        assert r.status_code == 200
        data = r.json()
        assert data["total"] == 2
        assert len(data["items"]) == 2
        assert data["offset"] == 0
        assert data["limit"] == 20

    @pytest.mark.asyncio
    async def test_non_admin_forbidden(self, client: AsyncClient, db: AsyncSession):
        await _make_admin(db)
        await _make_normal_user(db)

        token = await _token(client, "user", "userpass")
        r = await client.get("/admin/db/points-log", headers={"Authorization": f"Bearer {token}"})

        assert r.status_code == 403

    @pytest.mark.asyncio
    async def test_unauthenticated_rejected(self, client: AsyncClient, db: AsyncSession):
        await _make_admin(db)
        r = await client.get("/admin/db/points-log")
        assert r.status_code == 401

    @pytest.mark.asyncio
    async def test_pagination_offset_and_limit(self, client: AsyncClient, db: AsyncSession):
        await _make_admin(db)
        for i in range(5):
            await _make_points_log(db, person_name="Alice", points=i + 1)

        token = await _token(client, "admin", "adminpass")
        r = await client.get(
            "/admin/db/points-log?limit=2&offset=1",
            headers={"Authorization": f"Bearer {token}"},
        )
        assert r.status_code == 200
        data = r.json()
        assert data["total"] == 5
        assert len(data["items"]) == 2
        assert data["limit"] == 2
        assert data["offset"] == 1

    @pytest.mark.asyncio
    async def test_ordered_newest_first(self, client: AsyncClient, db: AsyncSession):
        await _make_admin(db)
        row1 = await _make_points_log(db, points=1)
        row2 = await _make_points_log(db, points=2)

        token = await _token(client, "admin", "adminpass")
        r = await client.get("/admin/db/points-log", headers={"Authorization": f"Bearer {token}"})
        items = r.json()["items"]
        # Newest entry (row2) should be first
        assert items[0]["id"] == row2.id
        assert items[1]["id"] == row1.id


# ---------------------------------------------------------------------------
# Tests: update (PATCH)
# ---------------------------------------------------------------------------

class TestUpdatePointsLog:
    @pytest.mark.asyncio
    async def test_admin_can_update_points(self, client: AsyncClient, db: AsyncSession):
        admin = await _make_admin(db)
        person = Person(name="Alice", username="alice", password_hash="x", points=10)
        db.add(person)
        await db.commit()

        row = await _make_points_log(db, person_name="alice", points=10)

        token = await _token(client, "admin", "adminpass")
        r = await client.patch(
            f"/admin/db/points-log/{row.id}",
            json={"points": 7, "person": "alice"},
            headers={"Authorization": f"Bearer {token}"},
        )
        assert r.status_code == 200
        data = r.json()
        assert data["points"] == 7

        # Person points adjusted: 10 + (7-10) = 7
        await db.refresh(person)
        assert person.points == 7

    @pytest.mark.asyncio
    async def test_update_writes_audit_log(self, client: AsyncClient, db: AsyncSession):
        await _make_admin(db)
        row = await _make_points_log(db, person_name="alice", points=5)

        token = await _token(client, "admin", "adminpass")
        await client.patch(
            f"/admin/db/points-log/{row.id}",
            json={"points": 3, "person": "alice"},
            headers={"Authorization": f"Bearer {token}"},
        )

        from sqlalchemy import select
        result = await db.execute(
            select(ChoreLog).where(ChoreLog.action == "admin_edit")
        )
        audit = result.scalars().all()
        assert len(audit) == 1
        assert "points" in audit[0].old_value
        assert audit[0].person == "admin"

    @pytest.mark.asyncio
    async def test_update_404_on_missing_row(self, client: AsyncClient, db: AsyncSession):
        await _make_admin(db)
        token = await _token(client, "admin", "adminpass")
        r = await client.patch(
            "/admin/db/points-log/99999",
            json={"points": 5, "person": "Nobody"},
            headers={"Authorization": f"Bearer {token}"},
        )
        assert r.status_code == 404

    @pytest.mark.asyncio
    async def test_non_admin_cannot_update(self, client: AsyncClient, db: AsyncSession):
        await _make_admin(db)
        await _make_normal_user(db)
        row = await _make_points_log(db)

        token = await _token(client, "user", "userpass")
        r = await client.patch(
            f"/admin/db/points-log/{row.id}",
            json={"points": 1, "person": "Alice"},
            headers={"Authorization": f"Bearer {token}"},
        )
        assert r.status_code == 403

    @pytest.mark.asyncio
    async def test_update_delta_path_uses_username(self, client: AsyncClient, db: AsyncSession):
        """Points-only change: lookup must use Person.username, not Person.name."""
        await _make_admin(db)
        person = Person(name="Alice", username="alice", password_hash="x", points=10)
        db.add(person)
        await db.commit()

        # PointsLog stores username (not display name)
        row = await _make_points_log(db, person_name="alice", points=10)

        token = await _token(client, "admin", "adminpass")
        r = await client.patch(
            f"/admin/db/points-log/{row.id}",
            json={"points": 7, "person": "alice"},
            headers={"Authorization": f"Bearer {token}"},
        )
        assert r.status_code == 200
        await db.refresh(person)
        assert person.points == 7  # 10 + (7-10) = 7

    @pytest.mark.asyncio
    async def test_update_reassigns_person_adjusts_both_points(self, client: AsyncClient, db: AsyncSession):
        """Reassign to different person (same points): old loses, new gains."""
        await _make_admin(db)
        alice = Person(name="Alice", username="alice", password_hash="x", points=10)
        bob = Person(name="Bob", username="bob", password_hash="x", points=0)
        db.add(alice)
        db.add(bob)
        await db.commit()

        row = await _make_points_log(db, person_name="alice", points=10)

        token = await _token(client, "admin", "adminpass")
        r = await client.patch(
            f"/admin/db/points-log/{row.id}",
            json={"points": 10, "person": "bob"},
            headers={"Authorization": f"Bearer {token}"},
        )
        assert r.status_code == 200
        await db.refresh(alice)
        await db.refresh(bob)
        assert alice.points == 0   # lost 10
        assert bob.points == 10    # gained 10

    @pytest.mark.asyncio
    async def test_update_person_and_points_simultaneously(self, client: AsyncClient, db: AsyncSession):
        """Change both person and points: old loses old_points, new gains new_points (no double-delta)."""
        await _make_admin(db)
        alice = Person(name="Alice", username="alice", password_hash="x", points=10)
        bob = Person(name="Bob", username="bob", password_hash="x", points=0)
        db.add(alice)
        db.add(bob)
        await db.commit()

        row = await _make_points_log(db, person_name="alice", points=10)

        token = await _token(client, "admin", "adminpass")
        r = await client.patch(
            f"/admin/db/points-log/{row.id}",
            json={"points": 5, "person": "bob"},
            headers={"Authorization": f"Bearer {token}"},
        )
        assert r.status_code == 200
        await db.refresh(alice)
        await db.refresh(bob)
        assert alice.points == 0   # lost exactly old_points=10 (not double-adjusted)
        assert bob.points == 5     # gained new_points=5

    @pytest.mark.asyncio
    async def test_update_missing_person_silently_skips(self, client: AsyncClient, db: AsyncSession):
        """Reassign to unknown username: update succeeds, no crash."""
        await _make_admin(db)
        row = await _make_points_log(db, person_name="ghost", points=5)

        token = await _token(client, "admin", "adminpass")
        r = await client.patch(
            f"/admin/db/points-log/{row.id}",
            json={"points": 5, "person": "ghost"},
            headers={"Authorization": f"Bearer {token}"},
        )
        assert r.status_code == 200

    @pytest.mark.asyncio
    async def test_update_legacy_display_name_in_log(self, client: AsyncClient, db: AsyncSession):
        """Old PointsLog rows storing display name (not username) still get points adjusted."""
        await _make_admin(db)
        # Person has display name 'Alice', username 'alice'
        person = Person(name="Alice", username="alice", password_hash="x", points=10)
        db.add(person)
        await db.commit()

        # Old-style row: person stored as display name, not username
        row = await _make_points_log(db, person_name="Alice", points=10)

        token = await _token(client, "admin", "adminpass")
        r = await client.patch(
            f"/admin/db/points-log/{row.id}",
            json={"points": 6, "person": "Alice"},
            headers={"Authorization": f"Bearer {token}"},
        )
        assert r.status_code == 200
        await db.refresh(person)
        assert person.points == 6  # 10 + (6-10) = 6


# ---------------------------------------------------------------------------
# Tests: delete (DELETE)
# ---------------------------------------------------------------------------

class TestDeletePointsLog:
    @pytest.mark.asyncio
    async def test_admin_can_delete(self, client: AsyncClient, db: AsyncSession):
        await _make_admin(db)
        person = Person(name="Alice", username="alice", password_hash="x", points=10)
        db.add(person)
        await db.commit()

        row = await _make_points_log(db, person_name="alice", points=10)

        token = await _token(client, "admin", "adminpass")
        r = await client.delete(
            f"/admin/db/points-log/{row.id}",
            headers={"Authorization": f"Bearer {token}"},
        )
        assert r.status_code == 204

        # Row is gone
        from sqlalchemy import select
        result = await db.execute(select(PointsLog).where(PointsLog.id == row.id))
        assert result.scalar_one_or_none() is None

    @pytest.mark.asyncio
    async def test_delete_reverses_points_on_person(self, client: AsyncClient, db: AsyncSession):
        await _make_admin(db)
        person = Person(name="Alice", username="alice", password_hash="x", points=15)
        db.add(person)
        await db.commit()

        row = await _make_points_log(db, person_name="alice", points=10)

        token = await _token(client, "admin", "adminpass")
        await client.delete(
            f"/admin/db/points-log/{row.id}",
            headers={"Authorization": f"Bearer {token}"},
        )

        await db.refresh(person)
        assert person.points == 5  # 15 - 10

    @pytest.mark.asyncio
    async def test_delete_floors_points_at_zero(self, client: AsyncClient, db: AsyncSession):
        await _make_admin(db)
        person = Person(name="Alice", username="alice", password_hash="x", points=3)
        db.add(person)
        await db.commit()

        row = await _make_points_log(db, person_name="alice", points=10)

        token = await _token(client, "admin", "adminpass")
        await client.delete(
            f"/admin/db/points-log/{row.id}",
            headers={"Authorization": f"Bearer {token}"},
        )

        await db.refresh(person)
        assert person.points == 0  # Never goes negative

    @pytest.mark.asyncio
    async def test_delete_writes_audit_log(self, client: AsyncClient, db: AsyncSession):
        await _make_admin(db)
        row = await _make_points_log(db, person_name="alice", points=5)

        token = await _token(client, "admin", "adminpass")
        await client.delete(
            f"/admin/db/points-log/{row.id}",
            headers={"Authorization": f"Bearer {token}"},
        )

        from sqlalchemy import select
        result = await db.execute(
            select(ChoreLog).where(ChoreLog.action == "admin_delete")
        )
        audit = result.scalars().all()
        assert len(audit) == 1
        assert audit[0].person == "admin"

    @pytest.mark.asyncio
    async def test_delete_404_on_missing_row(self, client: AsyncClient, db: AsyncSession):
        await _make_admin(db)
        token = await _token(client, "admin", "adminpass")
        r = await client.delete(
            "/admin/db/points-log/99999",
            headers={"Authorization": f"Bearer {token}"},
        )
        assert r.status_code == 404

    @pytest.mark.asyncio
    async def test_delete_reverses_points_uses_username(self, client: AsyncClient, db: AsyncSession):
        """Delete must look up Person by username, not display name."""
        await _make_admin(db)
        person = Person(name="Alice", username="alice", password_hash="x", points=15)
        db.add(person)
        await db.commit()

        row = await _make_points_log(db, person_name="alice", points=10)

        token = await _token(client, "admin", "adminpass")
        r = await client.delete(
            f"/admin/db/points-log/{row.id}",
            headers={"Authorization": f"Bearer {token}"},
        )
        assert r.status_code == 204
        await db.refresh(person)
        assert person.points == 5  # 15 - 10

    @pytest.mark.asyncio
    async def test_delete_legacy_display_name_in_log(self, client: AsyncClient, db: AsyncSession):
        """Old PointsLog rows storing display name still reverse points on delete."""
        await _make_admin(db)
        person = Person(name="Alice", username="alice", password_hash="x", points=15)
        db.add(person)
        await db.commit()

        # Old-style row: person stored as display name
        row = await _make_points_log(db, person_name="Alice", points=10)

        token = await _token(client, "admin", "adminpass")
        r = await client.delete(
            f"/admin/db/points-log/{row.id}",
            headers={"Authorization": f"Bearer {token}"},
        )
        assert r.status_code == 204
        await db.refresh(person)
        assert person.points == 5  # 15 - 10

    @pytest.mark.asyncio
    async def test_non_admin_cannot_delete(self, client: AsyncClient, db: AsyncSession):
        await _make_admin(db)
        await _make_normal_user(db)
        row = await _make_points_log(db)

        token = await _token(client, "user", "userpass")
        r = await client.delete(
            f"/admin/db/points-log/{row.id}",
            headers={"Authorization": f"Bearer {token}"},
        )
        assert r.status_code == 403
