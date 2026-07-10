"""Seed initial people and chores with comprehensive activity data.

Run once after first deploy to populate the database with realistic data
for development and upgrade regression testing.

Usage:
    python seed.py [--base-url http://localhost:8000]

The script:
1. Authenticates as admin (auto-creates admin on first login)
2. Creates People
3. Creates Chores
4. Seeds Completions, Skips, Reassignments, and Amendments (schedule/point updates)
"""
import asyncio
import sys
import httpx

BASE = "http://localhost:8000"


async def seed(base_url: str = BASE) -> None:
    async with httpx.AsyncClient(base_url=base_url, timeout=30) as c:
        # ------------------------------------------------------------------
        # Step 1: Login (auto-creates admin on first login if no users exist)
        # ------------------------------------------------------------------
        print("Logging in as admin...")
        login_r = await c.post("/v1/auth/login", json={"username": "admin", "password": "adminpass123"})
        if login_r.status_code != 200:
            print(f"Login failed: {login_r.status_code} {login_r.text}", file=sys.stderr)
            sys.exit(1)
        token = login_r.json()["access_token"]
        c.headers.update({"Authorization": f"Bearer {token}"})
        print("Login OK")

        # ------------------------------------------------------------------
        # Step 2: Create People
        # ------------------------------------------------------------------
        people = [
            {"name": "Derek", "username": "derek", "password": "derek_pass"},
            {"name": "Amy",   "username": "amy",   "password": "amy_pass"},
            {"name": "Connor","username": "connor", "password": "connor_pass"},
            {"name": "Lucas", "username": "lucas",  "password": "lucas_pass"},
        ]
        person_ids: dict[str, int] = {}
        for p in people:
            r = await c.post("/v1/people", json=p)
            if r.status_code in (200, 201):
                person_ids[p["name"]] = r.json()["id"]
                print(f"Person {p['name']}: {r.status_code}")
            elif r.status_code == 409:
                print(f"Person {p['name']}: already exists, skipping")
            else:
                print(f"Person {p['name']}: {r.status_code} {r.text}", file=sys.stderr)

        # ------------------------------------------------------------------
        # Step 3: Create Chores
        # ------------------------------------------------------------------
        chores_data = [
            {
                "name": "Vacuum downstairs",
                "schedule_type": "weekly",
                "schedule_config": {"days": ["mon", "thu"]},
                "assignment_type": "rotating",
                "eligible_people": ["Derek", "Amy", "Connor", "Lucas"],
                "points": 3,
            },
            {
                "name": "Clean bathrooms",
                "schedule_type": "weekly",
                "schedule_config": {"days": ["sat"]},
                "assignment_type": "rotating",
                "eligible_people": ["Derek", "Amy"],
                "points": 5,
            },
            {
                "name": "Mow lawn",
                "schedule_type": "interval",
                "schedule_config": {"days": 14},
                "assignment_type": "fixed",
                "assignee": "Derek",
                "eligible_people": [],
                "points": 4,
            },
            {
                "name": "Take out trash",
                "schedule_type": "weekly",
                "schedule_config": {"days": ["wed"]},
                "assignment_type": "open",
                "eligible_people": [],
                "points": 1,
            },
        ]

        chore_ids: dict[str, int] = {}
        for chore in chores_data:
            r = await c.post("/v1/chores", json=chore)
            if r.status_code in (200, 201):
                chore_ids[chore["name"]] = r.json()["id"]
                print(f"Chore '{chore['name']}': {r.status_code}")
            elif r.status_code == 409:
                # Already exists — fetch by listing
                print(f"Chore '{chore['name']}': already exists, skipping")
            else:
                print(f"Chore '{chore['name']}': {r.status_code} {r.text}", file=sys.stderr)

        if not chore_ids:
            print("No chores created; skipping activity seeding", file=sys.stderr)
            return

        # ------------------------------------------------------------------
        # Step 4: Completions — complete each chore once
        # ------------------------------------------------------------------
        print("\nSeeding completions...")
        for chore_name, chore_id in chore_ids.items():
            # Force state to due before completing
            await c.put(f"/v1/chores/{chore_id}", json={"state": "due"})
            r = await c.post(f"/v1/chores/{chore_id}/complete", json={"completed_by": "admin"})
            print(f"  Complete '{chore_name}': {r.status_code}")

        # ------------------------------------------------------------------
        # Step 5: Skips — skip the open chore
        # ------------------------------------------------------------------
        print("\nSeeding skips...")
        trash_id = chore_ids.get("Take out trash")
        if trash_id:
            await c.put(f"/v1/chores/{trash_id}", json={"state": "due"})
            r = await c.post(f"/v1/chores/{trash_id}/skip")
            print(f"  Skip 'Take out trash': {r.status_code}")

        # Also skip the lawn chore
        lawn_id = chore_ids.get("Mow lawn")
        if lawn_id:
            await c.put(f"/v1/chores/{lawn_id}", json={"state": "due"})
            r = await c.post(f"/v1/chores/{lawn_id}/skip")
            print(f"  Skip 'Mow lawn': {r.status_code}")

        # ------------------------------------------------------------------
        # Step 6: Reassignments — reassign the fixed chore to another person
        # ------------------------------------------------------------------
        print("\nSeeding reassignments...")
        vacuum_id = chore_ids.get("Vacuum downstairs")
        if vacuum_id:
            # Get current chore state to know who it's assigned to
            chore_r = await c.get(f"/v1/chores/{vacuum_id}")
            if chore_r.status_code == 200:
                current = chore_r.json().get("current_assignee")
                # Reassign to the next person in the rotation
                eligible = ["Derek", "Amy", "Connor", "Lucas"]
                if current in eligible:
                    idx = eligible.index(current)
                    new_assignee = eligible[(idx + 1) % len(eligible)]
                else:
                    new_assignee = "Amy"
                r = await c.post(f"/v1/chores/{vacuum_id}/reassign", json={"assignee": new_assignee})
                print(f"  Reassign 'Vacuum downstairs' → {new_assignee}: {r.status_code}")

        # ------------------------------------------------------------------
        # Step 7: Amendments — update schedule or points on chores
        # ------------------------------------------------------------------
        print("\nSeeding amendments...")
        # Update points on 'Clean bathrooms'
        bath_id = chore_ids.get("Clean bathrooms")
        if bath_id:
            r = await c.put(f"/v1/chores/{bath_id}", json={"points": 6})
            print(f"  Amend 'Clean bathrooms' points → 6: {r.status_code}")

        # Update schedule interval on 'Mow lawn'
        if lawn_id:
            r = await c.put(f"/v1/chores/{lawn_id}", json={
                "schedule_type": "interval",
                "schedule_config": {"days": 10},
            })
            print(f"  Amend 'Mow lawn' schedule → interval/10d: {r.status_code}")

        print("\nSeed complete.")


if __name__ == "__main__":
    base_url = BASE
    if len(sys.argv) > 1 and sys.argv[1] == "--base-url":
        base_url = sys.argv[2]
    asyncio.run(seed(base_url))
