import pytest


WEEKLY_CHORE = {
    "name": "Vacuum",
    "schedule_type": "weekly",
    "schedule_config": {"days": [0]},
    "assignment_type": "open",
    "eligible_people": [],
    "points": 5,
}

ROTATING_CHORE = {
    "name": "Dishes",
    "schedule_type": "interval",
    "schedule_config": {"days": 1},
    "assignment_type": "rotating",
    "eligible_people": ["Alice", "Bob"],
    "points": 3,
}


class TestPeopleAPI:
    @pytest.mark.asyncio
    async def test_create_and_list(self, authenticated_client):
        r = await authenticated_client.post("/people", json={"name": "Alice", "username": "alice"})
        assert r.status_code == 201
        assert r.json()["name"] == "Alice"

        r = await authenticated_client.get("/people")
        assert r.status_code == 200
        assert any(p["name"] == "Alice" for p in r.json())

    @pytest.mark.asyncio
    async def test_duplicate_rejected(self, authenticated_client):
        await authenticated_client.post("/people", json={"name": "Alice", "username": "alice"})
        r = await authenticated_client.post("/people", json={"name": "Alice", "username": "alice2"})
        assert r.status_code == 409

    @pytest.mark.asyncio
    async def test_delete_person(self, authenticated_client):
        create_r = await authenticated_client.post("/people", json={"name": "Bob", "username": "bob"})
        person_id = create_r.json()["id"]
        r = await authenticated_client.delete(f"/people/{person_id}")
        assert r.status_code == 204

        r = await authenticated_client.get("/people")
        assert not any(p["name"] == "Bob" for p in r.json())

    @pytest.mark.asyncio
    async def test_delete_nonexistent(self, authenticated_client):
        r = await authenticated_client.delete("/people/99999")
        assert r.status_code == 404

    @pytest.mark.asyncio
    async def test_create_person_has_defaults(self, authenticated_client):
        r = await authenticated_client.post("/people", json={"name": "Alex", "username": "alex"})
        assert r.status_code == 201
        data = r.json()
        assert data["name"] == "Alex"
        assert "id" in data
        assert "color" in data
        assert "goal_7d" in data
        assert "goal_30d" in data
        assert data["goal_7d"] == 20
        assert data["goal_30d"] == 80

    @pytest.mark.asyncio
    async def test_person_has_username_field(self, authenticated_client):
        r = await authenticated_client.post("/people", json={"name": "Charlie", "username": "charlie123"})
        assert r.status_code == 201
        data = r.json()
        assert data["username"] == "charlie123"
        assert "password_hash" not in data  # Never return password hash

    @pytest.mark.asyncio
    async def test_person_has_is_admin_field(self, authenticated_client):
        r = await authenticated_client.post("/people", json={"name": "David", "username": "david123"})
        assert r.status_code == 201
        data = r.json()
        assert "is_admin" in data
        assert isinstance(data["is_admin"], bool)

    @pytest.mark.asyncio
    async def test_username_uniqueness_enforced(self, authenticated_client):
        await authenticated_client.post("/people", json={"name": "Eve", "username": "eve123"})
        r = await authenticated_client.post("/people", json={"name": "Frank", "username": "eve123"})
        assert r.status_code == 409  # Conflict - duplicate username


class TestChoresAPI:
    @pytest.mark.asyncio
    async def test_create_chore(self, authenticated_client):
        r = await authenticated_client.post("/chores", json=WEEKLY_CHORE)
        assert r.status_code == 201
        data = r.json()
        assert data["name"] == "Vacuum"
        assert "id" in data
        assert isinstance(data["id"], int)
        assert data["schedule_summary"] == "Weekly on Mon"

    @pytest.mark.asyncio
    async def test_list_chores(self, authenticated_client):
        await authenticated_client.post("/chores", json=WEEKLY_CHORE)
        r = await authenticated_client.get("/chores")
        assert r.status_code == 200
        assert len(r.json()) == 1

    @pytest.mark.asyncio
    async def test_get_chore(self, authenticated_client):
        create_r = await authenticated_client.post("/chores", json=WEEKLY_CHORE)
        chore_id = create_r.json()["id"]
        r = await authenticated_client.get(f"/chores/{chore_id}")
        assert r.status_code == 200
        assert r.json()["name"] == "Vacuum"

    @pytest.mark.asyncio
    async def test_get_nonexistent(self, authenticated_client):
        r = await authenticated_client.get("/chores/99999")
        assert r.status_code == 404

    @pytest.mark.asyncio
    async def test_duplicate_rejected(self, authenticated_client):
        await authenticated_client.post("/chores", json=WEEKLY_CHORE)
        r = await authenticated_client.post("/chores", json=WEEKLY_CHORE)
        assert r.status_code == 409

    @pytest.mark.asyncio
    async def test_update_chore(self, authenticated_client):
        create_r = await authenticated_client.post("/chores", json=WEEKLY_CHORE)
        chore_id = create_r.json()["id"]
        r = await authenticated_client.put(f"/chores/{chore_id}", json={"points": 10})
        assert r.status_code == 200
        assert r.json()["points"] == 10

    @pytest.mark.asyncio
    async def test_update_fixed_assignee_updates_current_assignee(self, authenticated_client):
        await authenticated_client.post("/people", json={"name": "Alice", "username": "alice"})
        await authenticated_client.post("/people", json={"name": "Bob", "username": "bob"})
        create_r = await authenticated_client.post(
            "/chores",
            json={
                "name": "Feed cat",
                "schedule_type": "weekly",
                "schedule_config": {"days": [0]},
                "assignment_type": "fixed",
                "assignee": "Alice",
                "points": 1,
            },
        )
        chore_id = create_r.json()["id"]

        r = await authenticated_client.put(f"/chores/{chore_id}", json={"assignee": "Bob"})
        assert r.status_code == 200
        data = r.json()
        assert data["assignee"] == "Bob"
        assert data["current_assignee"] == "Bob"

    @pytest.mark.asyncio
    async def test_update_rotating_current_and_next_assignee(self, authenticated_client):
        await authenticated_client.post("/people", json={"name": "Alice", "username": "alice"})
        await authenticated_client.post("/people", json={"name": "Bob", "username": "bob"})
        await authenticated_client.post("/people", json={"name": "Carol", "username": "carol"})
        create_r = await authenticated_client.post(
            "/chores",
            json={
                "name": "Laundry",
                "schedule_type": "interval",
                "schedule_config": {"days": 3},
                "assignment_type": "rotating",
                "eligible_people": ["Alice", "Bob", "Carol"],
                "points": 2,
            },
        )
        chore_id = create_r.json()["id"]

        r = await authenticated_client.put(
            f"/chores/{chore_id}",
            json={"current_assignee": "Bob", "next_assignee": "Carol"},
        )
        assert r.status_code == 200
        data = r.json()
        assert data["current_assignee"] == "Bob"
        assert data["next_assignee"] == "Carol"
        assert data["rotation_index"] == 1

    @pytest.mark.asyncio
    async def test_unassign_open_chore(self, authenticated_client):
        await authenticated_client.post("/people", json={"name": "Alice", "username": "alice"})
        create_r = await authenticated_client.post(
            "/chores",
            json={
                "name": "Dishes",
                "schedule_type": "weekly",
                "schedule_config": {"days": [0]},
                "assignment_type": "open",
                "points": 1,
            },
        )
        chore_id = create_r.json()["id"]

        # Assign to Alice
        r = await authenticated_client.put(
            f"/chores/{chore_id}",
            json={"current_assignee": "Alice"},
        )
        assert r.status_code == 200
        assert r.json()["current_assignee"] == "Alice"

        # Unassign (set to null)
        r = await authenticated_client.put(
            f"/chores/{chore_id}",
            json={"current_assignee": None},
        )
        assert r.status_code == 200
        assert r.json()["current_assignee"] is None

        # Verify by fetching chore again
        r = await authenticated_client.get(f"/chores/{chore_id}")
        assert r.status_code == 200
        assert r.json()["current_assignee"] is None

    @pytest.mark.asyncio
    async def test_update_next_due_from_past_to_future_resets_state_to_complete(self, authenticated_client):
        from datetime import date, timedelta

        # Create a chore (will have next_due calculated from schedule)
        create_r = await authenticated_client.post("/chores", json=WEEKLY_CHORE)
        chore_id = create_r.json()["id"]
        initial_state = create_r.json()["state"]

        # Update next_due to a past date (should set state to "due")
        past_date = (date.today() - timedelta(days=1)).isoformat()
        r = await authenticated_client.put(f"/chores/{chore_id}", json={"next_due": past_date})
        assert r.status_code == 200
        assert r.json()["state"] == "due"
        assert r.json()["next_due"] == past_date

        # Update next_due to a future date (should reset state to "complete")
        future_date = (date.today() + timedelta(days=5)).isoformat()
        r = await authenticated_client.put(f"/chores/{chore_id}", json={"next_due": future_date})
        assert r.status_code == 200
        assert r.json()["state"] == "complete"
        assert r.json()["next_due"] == future_date

    @pytest.mark.asyncio
    async def test_update_next_due_to_today_sets_state_to_due(self, authenticated_client):
        from datetime import date, timedelta

        # Create a chore
        create_r = await authenticated_client.post("/chores", json=WEEKLY_CHORE)
        chore_id = create_r.json()["id"]

        # First set to a future date
        future_date = (date.today() + timedelta(days=5)).isoformat()
        await authenticated_client.put(f"/chores/{chore_id}", json={"next_due": future_date})

        # Update next_due to today (should set state to "due")
        today = date.today().isoformat()
        r = await authenticated_client.put(f"/chores/{chore_id}", json={"next_due": today})
        assert r.status_code == 200
        assert r.json()["state"] == "due"
        assert r.json()["next_due"] == today

    @pytest.mark.asyncio
    async def test_update_next_due_back_to_future_resets_complete(self, authenticated_client):
        from datetime import date, timedelta

        # Create a chore
        create_r = await authenticated_client.post("/chores", json=WEEKLY_CHORE)
        chore_id = create_r.json()["id"]

        # Set next_due to past date (state becomes "due")
        past_date = (date.today() - timedelta(days=2)).isoformat()
        r = await authenticated_client.put(f"/chores/{chore_id}", json={"next_due": past_date})
        assert r.status_code == 200
        assert r.json()["state"] == "due"

        # Update next_due back to future (state should go back to "complete")
        future_date = (date.today() + timedelta(days=7)).isoformat()
        r = await authenticated_client.put(f"/chores/{chore_id}", json={"next_due": future_date})
        assert r.status_code == 200
        assert r.json()["state"] == "complete"
        assert r.json()["next_due"] == future_date

    @pytest.mark.asyncio
    async def test_update_next_due_with_assignment_changes(self, authenticated_client):
        from datetime import date, timedelta

        # Set up people for assignment test
        await authenticated_client.post("/people", json={"name": "Alice", "username": "alice"})
        await authenticated_client.post("/people", json={"name": "Bob", "username": "bob"})

        # Create a fixed assignment chore
        create_r = await authenticated_client.post(
            "/chores",
            json={
                "name": "Feed cat",
                "schedule_type": "weekly",
                "schedule_config": {"days": [0]},
                "assignment_type": "fixed",
                "assignee": "Alice",
                "points": 1,
            },
        )
        chore_id = create_r.json()["id"]
        assert create_r.json()["assignee"] == "Alice"

        # Update both next_due to past date and assignee to Bob
        past_date = (date.today() - timedelta(days=1)).isoformat()
        r = await authenticated_client.put(
            f"/chores/{chore_id}",
            json={"next_due": past_date, "assignee": "Bob"},
        )
        assert r.status_code == 200
        assert r.json()["state"] == "due"
        assert r.json()["next_due"] == past_date
        assert r.json()["assignee"] == "Bob"
        assert r.json()["current_assignee"] == "Bob"

        # Update to future date
        future_date = (date.today() + timedelta(days=5)).isoformat()
        r = await authenticated_client.put(f"/chores/{chore_id}", json={"next_due": future_date})
        assert r.status_code == 200
        assert r.json()["state"] == "complete"
        assert r.json()["next_due"] == future_date
        assert r.json()["assignee"] == "Bob"

    @pytest.mark.asyncio
    async def test_delete_chore(self, authenticated_client):
        create_r = await authenticated_client.post("/chores", json=WEEKLY_CHORE)
        chore_id = create_r.json()["id"]
        r = await authenticated_client.delete(f"/chores/{chore_id}")
        assert r.status_code == 204

        r = await authenticated_client.get(f"/chores/{chore_id}")
        assert r.status_code == 404

    @pytest.mark.asyncio
    async def test_complete_action(self, authenticated_client):
        r = await authenticated_client.post("/chores", json=WEEKLY_CHORE)
        chore_id = r.json()["id"]

        # Force to due so we can complete it
        await authenticated_client.post(f"/chores/{chore_id}/mark-due")
        r = await authenticated_client.post(f"/chores/{chore_id}/complete", json={"completed_by": "Alice"})
        assert r.status_code == 200
        assert r.json()["state"] == "complete"
        assert r.json()["last_completed_by"] == "Alice"

    @pytest.mark.asyncio
    async def test_skip_action(self, authenticated_client):
        r = await authenticated_client.post("/chores", json=WEEKLY_CHORE)
        chore_id = r.json()["id"]
        await authenticated_client.post(f"/chores/{chore_id}/mark-due")

        r = await authenticated_client.post(f"/chores/{chore_id}/skip")
        assert r.status_code == 200
        assert r.json()["state"] == "complete"
        assert r.json()["last_change_type"] == "skipped"

    @pytest.mark.asyncio
    async def test_reassign_action(self, authenticated_client):
        await authenticated_client.post("/people", json={"name": "Alice", "username": "alice"})
        await authenticated_client.post("/people", json={"name": "Bob", "username": "bob"})
        r = await authenticated_client.post("/chores", json=ROTATING_CHORE)
        chore_id = r.json()["id"]

        r = await authenticated_client.post(f"/chores/{chore_id}/reassign", json={"assignee": "Bob"})
        assert r.status_code == 200
        assert r.json()["current_assignee"] == "Bob"

    @pytest.mark.asyncio
    async def test_mark_due_action(self, authenticated_client):
        r = await authenticated_client.post("/chores", json=WEEKLY_CHORE)
        chore_id = r.json()["id"]
        await authenticated_client.post(f"/chores/{chore_id}/complete", json={})

        r = await authenticated_client.post(f"/chores/{chore_id}/mark-due")
        assert r.status_code == 200
        assert r.json()["state"] == "due"

    @pytest.mark.asyncio
    async def test_mark_due_action_updates_next_due_to_today(self, authenticated_client):
        from datetime import date, timedelta

        r = await authenticated_client.post("/chores", json=WEEKLY_CHORE)
        chore_id = r.json()["id"]
        original_next_due = r.json()["next_due"]

        # Set next_due to future
        future_date = (date.today() + timedelta(days=5)).isoformat()
        await authenticated_client.put(f"/chores/{chore_id}", json={"next_due": future_date})

        # Mark due should set next_due to today
        r = await authenticated_client.post(f"/chores/{chore_id}/mark-due")
        assert r.status_code == 200
        assert r.json()["state"] == "due"
        assert r.json()["next_due"] == date.today().isoformat()

    @pytest.mark.asyncio
    async def test_skip_reassign_action(self, authenticated_client):
        await authenticated_client.post("/people", json={"name": "Alice", "username": "alice"})
        await authenticated_client.post("/people", json={"name": "Bob", "username": "bob"})
        r = await authenticated_client.post("/chores", json=ROTATING_CHORE)
        chore_id = r.json()["id"]
        await authenticated_client.post(f"/chores/{chore_id}/mark-due")

        r = await authenticated_client.post(f"/chores/{chore_id}/skip-reassign", json={"assignee": "Bob"})
        assert r.status_code == 200
        data = r.json()
        assert data["state"] == "complete"
        assert data["current_assignee"] == "Bob"

    @pytest.mark.asyncio
    async def test_reject_invalid_eligible_people(self, authenticated_client):
        invalid_chore = {
            "name": "Invalid Chore",
            "schedule_type": "weekly",
            "schedule_config": {"days": [0]},
            "assignment_type": "rotating",
            "eligible_people": ["NonExistent"],
            "points": 5,
        }
        r = await authenticated_client.post("/chores", json=invalid_chore)
        assert r.status_code == 400

    @pytest.mark.asyncio
    async def test_reject_invalid_fixed_assignee(self, authenticated_client):
        invalid_chore = {
            "name": "Invalid Fixed",
            "schedule_type": "weekly",
            "schedule_config": {"days": [0]},
            "assignment_type": "fixed",
            "assignee": "NonExistent",
            "points": 5,
        }
        r = await authenticated_client.post("/chores", json=invalid_chore)
        assert r.status_code == 400


class TestPointsAPI:
    @pytest.mark.asyncio
    async def test_leaderboard_empty(self, authenticated_client):
        r = await authenticated_client.get("/points")
        assert r.status_code == 200
        assert r.json() == []

    @pytest.mark.asyncio
    async def test_leaderboard_after_completion(self, authenticated_client):
        r = await authenticated_client.post("/chores", json=WEEKLY_CHORE)
        chore_id = r.json()["id"]
        await authenticated_client.post(f"/chores/{chore_id}/mark-due")
        await authenticated_client.post(f"/chores/{chore_id}/complete", json={"completed_by": "Alice"})

        r = await authenticated_client.get("/points")
        assert r.status_code == 200
        data = r.json()
        assert len(data) == 1
        assert data[0]["person"] == "Alice"
        assert data[0]["total_points"] == 5

    @pytest.mark.asyncio
    async def test_person_history(self, authenticated_client):
        r = await authenticated_client.post("/chores", json=WEEKLY_CHORE)
        chore_id = r.json()["id"]
        await authenticated_client.post(f"/chores/{chore_id}/mark-due")
        await authenticated_client.post(f"/chores/{chore_id}/complete", json={"completed_by": "Alice"})

        r = await authenticated_client.get("/points/Alice")
        assert r.status_code == 200
        data = r.json()
        assert len(data) == 1
        assert data[0]["points"] == 5

    @pytest.mark.asyncio
    async def test_points_summary_empty(self, authenticated_client):
        r = await authenticated_client.get("/points/summary")
        assert r.status_code == 200
        # TestUser created by authenticated_client fixture
        summary = r.json()
        assert len(summary) == 1
        assert summary[0]["person"] == "TestUser"
        assert summary[0]["points_7d"] == 0
        assert summary[0]["points_30d"] == 0

    @pytest.mark.asyncio
    async def test_points_summary_includes_all_people(self, authenticated_client):
        await authenticated_client.post("/people", json={"name": "Alice", "username": "alice"})
        await authenticated_client.post("/people", json={"name": "Bob", "username": "bob"})
        r = await authenticated_client.get("/points/summary")
        assert r.status_code == 200
        names = [e["person"] for e in r.json()]
        assert "Alice" in names
        assert "Bob" in names

    @pytest.mark.asyncio
    async def test_points_summary_counts_recent(self, authenticated_client):
        await authenticated_client.post("/people", json={"name": "Alice", "username": "alice"})
        r = await authenticated_client.post("/chores", json=WEEKLY_CHORE)
        chore_id = r.json()["id"]
        await authenticated_client.post(f"/chores/{chore_id}/mark-due")
        await authenticated_client.post(f"/chores/{chore_id}/complete", json={"completed_by": "Alice"})

        r = await authenticated_client.get("/points/summary")
        alice = next(e for e in r.json() if e["person"] == "Alice")
        assert alice["points_7d"] == 5
        assert alice["points_30d"] == 5

    @pytest.mark.asyncio
    async def test_points_summary_zero_for_no_activity(self, authenticated_client):
        await authenticated_client.post("/people", json={"name": "Bob", "username": "bob"})
        r = await authenticated_client.get("/points/summary")
        bob = next(e for e in r.json() if e["person"] == "Bob")
        assert bob["points_7d"] == 0
        assert bob["points_30d"] == 0

    @pytest.mark.asyncio
    async def test_health(self, authenticated_client):
        r = await authenticated_client.get("/health")
        assert r.status_code == 200
        assert r.json() == {"status": "ok"}


class TestLogAPI:
    @pytest.mark.asyncio
    async def test_log_filters_multiple_actions(self, authenticated_client):
        await authenticated_client.post("/people", json={"name": "Alice", "username": "alice"})
        await authenticated_client.post("/people", json={"name": "Bob", "username": "bob"})
        r = await authenticated_client.post("/chores", json=ROTATING_CHORE)
        chore_id = r.json()["id"]

        await authenticated_client.post(f"/chores/{chore_id}/mark-due")
        await authenticated_client.post(f"/chores/{chore_id}/complete", json={"completed_by": "Alice"})
        await authenticated_client.post(f"/chores/{chore_id}/reassign", json={"assignee": "Bob"})
        await authenticated_client.put(f"/chores/{chore_id}", json={"points": 9})

        r = await authenticated_client.get("/log?person=Alice&actions=completed&actions=reassigned")
        assert r.status_code == 200
        actions = [entry["action"] for entry in r.json()]
        assert "completed" in actions
        assert "reassigned" not in actions

        r = await authenticated_client.get("/log?actions=completed&actions=reassigned")
        assert r.status_code == 200
        actions = [entry["action"] for entry in r.json()]
        assert "completed" in actions
        assert "reassigned" in actions
        assert "updated" not in actions
