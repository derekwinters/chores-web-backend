"""Seed initial people and chores. Run once after first deploy."""
import asyncio
import httpx

BASE = "http://localhost:8000"


async def seed():
    async with httpx.AsyncClient(base_url=BASE, timeout=10) as c:
        for name in ["Derek", "Amy", "Connor", "Lucas"]:
            r = await c.post("/people", json={"name": name})
            print(f"Person {name}: {r.status_code}")

        chores = [
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

        for chore in chores:
            r = await c.post("/chores", json=chore)
            print(f"Chore {chore['name']}: {r.status_code}")


asyncio.run(seed())
