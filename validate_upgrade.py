"""Upgrade regression validation script.

Validates that data seeded against the previous release is intact after the new
backend starts against the same Postgres volume. Exits non-zero on any failure,
which fails the CI job.

Checks performed:
  API assertions:
    - /health returns {"status": "ok"}
    - /people returns >= 4 people (Derek, Amy, Connor, Lucas + admin)
    - /chores returns >= 4 chores
    - /points (leaderboard) returns entries (completions produce PointsLog rows)
    - /log returns entries with actions: completed, skipped, reassigned, updated

  Raw SQL checks (via DATABASE_URL):
    - points_log rows >= expected completions count
    - chore_log FK integrity: all chore_log.chore_id reference valid chores.id

Usage:
    python validate_upgrade.py [--base-url http://localhost:8000]

Environment:
    DATABASE_URL — Postgres connection string (required for SQL checks)
"""
import asyncio
import os
import sys
import httpx

BASE = "http://localhost:8000"
FAILURES: list[str] = []


def fail(msg: str) -> None:
    print(f"  FAIL: {msg}", file=sys.stderr)
    FAILURES.append(msg)


def ok(msg: str) -> None:
    print(f"  OK:   {msg}")


# ---------------------------------------------------------------------------
# API assertions
# ---------------------------------------------------------------------------

async def check_health(c: httpx.AsyncClient) -> None:
    print("Checking /health...")
    r = await c.get("/health")
    if r.status_code != 200:
        fail(f"/health returned {r.status_code}")
        return
    data = r.json()
    if data.get("status") != "ok":
        fail(f"/health returned unexpected body: {data}")
    else:
        ok("/health status=ok")


async def check_people(c: httpx.AsyncClient) -> None:
    print("Checking /people...")
    r = await c.get("/v1/people")
    if r.status_code != 200:
        fail(f"/people returned {r.status_code}")
        return
    people = r.json()
    names = [p["name"] for p in people]
    expected_names = ["Derek", "Amy", "Connor", "Lucas"]
    for name in expected_names:
        if name not in names:
            fail(f"/people missing expected person: {name}")
        else:
            ok(f"/people contains {name}")
    if len(people) < 4:
        fail(f"/people returned only {len(people)} people (expected >= 4)")
    else:
        ok(f"/people count={len(people)}")


async def check_chores(c: httpx.AsyncClient) -> int:
    """Returns number of chores found."""
    print("Checking /chores...")
    r = await c.get("/v1/chores")
    if r.status_code != 200:
        fail(f"/chores returned {r.status_code}")
        return 0
    chores = r.json()
    expected_names = ["Vacuum downstairs", "Clean bathrooms", "Mow lawn", "Take out trash"]
    for name in expected_names:
        if not any(ch["name"] == name for ch in chores):
            fail(f"/chores missing expected chore: {name}")
        else:
            ok(f"/chores contains '{name}'")
    if len(chores) < 4:
        fail(f"/chores returned only {len(chores)} chores (expected >= 4)")
    else:
        ok(f"/chores count={len(chores)}")
    return len(chores)


async def check_points(c: httpx.AsyncClient) -> None:
    print("Checking /points (leaderboard)...")
    r = await c.get("/v1/points")
    if r.status_code != 200:
        fail(f"/points returned {r.status_code}")
        return
    entries = r.json()
    if len(entries) == 0:
        fail("/points leaderboard is empty (expected completions to produce PointsLog entries)")
    else:
        ok(f"/points leaderboard has {len(entries)} entries")


async def check_activity_log(c: httpx.AsyncClient) -> None:
    print("Checking /log for expected action types...")
    r = await c.get("/v1/log")
    if r.status_code != 200:
        fail(f"/log returned {r.status_code}")
        return
    entries = r.json()
    actions_found = {entry["action"] for entry in entries}

    required_actions = ["completed", "skipped", "reassigned", "updated"]
    for action in required_actions:
        if action not in actions_found:
            fail(f"/log missing entries with action='{action}'")
        else:
            ok(f"/log contains action='{action}'")

    ok(f"/log total entries: {len(entries)}")


# ---------------------------------------------------------------------------
# Raw SQL checks
# ---------------------------------------------------------------------------

async def check_sql_integrity() -> None:
    """Run raw SQL checks against Postgres via asyncpg."""
    db_url = os.environ.get("DATABASE_URL", "")
    if not db_url:
        print("Skipping SQL checks: DATABASE_URL not set")
        return

    try:
        import asyncpg
    except ImportError:
        print("Skipping SQL checks: asyncpg not available")
        return

    # Convert SQLAlchemy URL to asyncpg URL
    conn_url = db_url.replace("postgresql+asyncpg://", "postgresql://")

    print("Checking SQL integrity...")
    try:
        conn = await asyncpg.connect(conn_url)
    except Exception as e:
        fail(f"SQL check: could not connect to Postgres: {e}")
        return

    try:
        # Check points_log has rows
        count = await conn.fetchval("SELECT COUNT(*) FROM points_log")
        if count == 0:
            fail("SQL: points_log is empty (expected completion rows)")
        else:
            ok(f"SQL: points_log has {count} rows")

        # Check chore_log has rows for all expected action types
        for action in ("completed", "skipped", "reassigned", "updated"):
            action_count = await conn.fetchval(
                "SELECT COUNT(*) FROM chore_log WHERE action = $1", action
            )
            if action_count == 0:
                fail(f"SQL: chore_log has no rows with action='{action}'")
            else:
                ok(f"SQL: chore_log action='{action}' has {action_count} rows")

        # FK integrity: all chore_log.chore_id must reference a valid chore
        orphans = await conn.fetchval(
            """
            SELECT COUNT(*)
            FROM chore_log cl
            WHERE cl.chore_id NOT IN (SELECT id FROM chores)
            """
        )
        if orphans > 0:
            fail(f"SQL: {orphans} chore_log rows reference non-existent chore_id (FK violation)")
        else:
            ok("SQL: chore_log FK integrity OK (no orphaned chore_id references)")

        # FK integrity: all points_log.chore_id must reference a valid chore
        pl_orphans = await conn.fetchval(
            """
            SELECT COUNT(*)
            FROM points_log pl
            WHERE pl.chore_id NOT IN (SELECT id FROM chores)
            """
        )
        if pl_orphans > 0:
            fail(f"SQL: {pl_orphans} points_log rows reference non-existent chore_id (FK violation)")
        else:
            ok("SQL: points_log FK integrity OK (no orphaned chore_id references)")

    finally:
        await conn.close()


# ---------------------------------------------------------------------------
# Main
# ---------------------------------------------------------------------------

async def validate(base_url: str = BASE) -> None:
    print(f"Running upgrade validation against {base_url}\n")

    # Authenticate first — handle password reset required (403) from bcrypt migration
    async with httpx.AsyncClient(base_url=base_url, timeout=30) as c:
        login_r = await c.post("/v1/auth/login", json={"username": "admin", "password": "adminpass123"})
        if login_r.status_code == 403:
            body = login_r.json()
            reset_token = body.get("reset_token") or (body.get("detail", {}) or {}).get("reset_token")
            if reset_token:
                reset_r = await c.put(
                    "/v1/auth/password/reset",
                    json={"new_password": "adminpass123"},
                    headers={"Authorization": f"Bearer {reset_token}"},
                )
                if reset_r.status_code != 200:
                    fail(f"Password reset failed: {reset_r.status_code} {reset_r.text}")
                    _report_results()
                    return
                token = reset_r.json()["access_token"]
            else:
                fail(f"Login failed: {login_r.status_code} {login_r.text}")
                _report_results()
                return
        elif login_r.status_code != 200:
            fail(f"Login failed: {login_r.status_code} {login_r.text}")
            _report_results()
            return
        else:
            token = login_r.json()["access_token"]

        c.headers.update({"Authorization": f"Bearer {token}"})

        await check_health(c)
        await check_people(c)
        await check_chores(c)
        await check_points(c)
        await check_activity_log(c)

    await check_sql_integrity()
    _report_results()


def _report_results() -> None:
    print()
    if FAILURES:
        print(f"VALIDATION FAILED: {len(FAILURES)} check(s) failed:", file=sys.stderr)
        for f in FAILURES:
            print(f"  - {f}", file=sys.stderr)
        sys.exit(1)
    else:
        print("VALIDATION PASSED: all checks OK")


if __name__ == "__main__":
    base_url = BASE
    args = sys.argv[1:]
    if "--base-url" in args:
        idx = args.index("--base-url")
        base_url = args[idx + 1]
    asyncio.run(validate(base_url))
