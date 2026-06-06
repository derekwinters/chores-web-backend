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
        r = await authenticated_client.post("/v1/people", json={"name": "Alice", "username": "alice"})
        assert r.status_code == 201
        assert r.json()["name"] == "Alice"

        r = await authenticated_client.get("/v1/people")
        assert r.status_code == 200
        assert any(p["name"] == "Alice" for p in r.json())

    @pytest.mark.asyncio
    async def test_duplicate_rejected(self, authenticated_client):
        await authenticated_client.post("/v1/people", json={"name": "Alice", "username": "alice"})
        r = await authenticated_client.post("/v1/people", json={"name": "Alice", "username": "alice2"})
        assert r.status_code == 409

    @pytest.mark.asyncio
    async def test_delete_person(self, authenticated_client):
        create_r = await authenticated_client.post("/v1/people", json={"name": "Bob", "username": "bob"})
        person_id = create_r.json()["id"]
        r = await authenticated_client.delete(f"/v1/people/{person_id}")
        assert r.status_code == 204

        r = await authenticated_client.get("/v1/people")
        assert not any(p["name"] == "Bob" for p in r.json())

    @pytest.mark.asyncio
    async def test_delete_nonexistent(self, authenticated_client):
        r = await authenticated_client.delete("/v1/people/99999")
        assert r.status_code == 404

    @pytest.mark.asyncio
    async def test_create_person_has_defaults(self, authenticated_client):
        r = await authenticated_client.post("/v1/people", json={"name": "Alex", "username": "alex"})
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
        r = await authenticated_client.post("/v1/people", json={"name": "Charlie", "username": "charlie123"})
        assert r.status_code == 201
        data = r.json()
        assert data["username"] == "charlie123"
        assert "password_hash" not in data  # Never return password hash

    @pytest.mark.asyncio
    async def test_person_has_is_admin_field(self, authenticated_client):
        r = await authenticated_client.post("/v1/people", json={"name": "David", "username": "david123"})
        assert r.status_code == 201
        data = r.json()
        assert "is_admin" in data
        assert isinstance(data["is_admin"], bool)

    @pytest.mark.asyncio
    async def test_username_uniqueness_enforced(self, authenticated_client):
        await authenticated_client.post("/v1/people", json={"name": "Eve", "username": "eve123"})
        r = await authenticated_client.post("/v1/people", json={"name": "Frank", "username": "eve123"})
        assert r.status_code == 409  # Conflict - duplicate username

    @pytest.mark.asyncio
    async def test_person_has_points_field_with_default(self, authenticated_client):
        r = await authenticated_client.post("/v1/people", json={"name": "George", "username": "george123"})
        assert r.status_code == 201
        data = r.json()
        assert "points" in data
        assert data["points"] == 0

    @pytest.mark.asyncio
    async def test_points_auto_update_on_chore_completion(self, authenticated_client):
        chore_r = await authenticated_client.post("/v1/chores", json={
            "name": "Test Chore",
            "schedule_type": "interval",
            "schedule_config": {"days": 1},
            "points": 25
        })
        chore_id = chore_r.json()["id"]

        # Complete chore (points credited to authenticated user: testuser)
        await authenticated_client.post(f"/v1/chores/{chore_id}/complete", json={})

        # Check testuser points updated
        people_r = await authenticated_client.get(f"/v1/people")
        testuser = next((p for p in people_r.json() if p["username"] == "testuser"), None)
        assert testuser is not None
        assert testuser["points"] == 25

    @pytest.mark.asyncio
    async def test_points_cannot_be_manually_set(self, authenticated_client):
        create_r = await authenticated_client.post("/v1/people", json={"name": "Ivan", "username": "ivan"})
        person_id = create_r.json()["id"]

        # Try to set points via update - should be ignored
        r = await authenticated_client.put(f"/v1/people/{person_id}", json={"points": 100})
        assert r.status_code == 200
        # Points should still be 0 (not 100)
        assert r.json()["points"] == 0

    @pytest.mark.asyncio
    async def test_multiple_completions_accumulate_points(self, authenticated_client):
        chore_r = await authenticated_client.post("/v1/chores", json={
            "name": "Test Chore",
            "schedule_type": "interval",
            "schedule_config": {"days": 1},
            "points": 30
        })
        chore_id = chore_r.json()["id"]

        # Complete twice (points credited to authenticated user: testuser)
        await authenticated_client.post(f"/v1/chores/{chore_id}/complete", json={})
        await authenticated_client.post(f"/v1/chores/{chore_id}/complete", json={})

        # Check total points for testuser
        people_r = await authenticated_client.get(f"/v1/people")
        testuser = next((p for p in people_r.json() if p["username"] == "testuser"), None)
        assert testuser is not None
        assert testuser["points"] == 60

    @pytest.mark.asyncio
    async def test_redemption_history_empty(self, authenticated_client):
        create_r = await authenticated_client.post("/v1/people", json={"name": "Karen", "username": "karen"})
        person_id = create_r.json()["id"]

        r = await authenticated_client.get(f"/v1/people/{person_id}/redemptions")
        assert r.status_code == 200
        assert r.json() == []

    @pytest.mark.asyncio
    async def test_redemption_history_not_found(self, authenticated_client):
        r = await authenticated_client.get(f"/v1/people/999/redemptions")
        assert r.status_code == 404

    @pytest.mark.asyncio
    async def test_redemption_history_after_redemption(self, authenticated_client):
        # Create and complete chore to earn points
        chore_r = await authenticated_client.post("/v1/chores", json={
            "name": "Test",
            "schedule_type": "interval",
            "schedule_config": {"days": 1},
            "points": 50
        })
        chore_id = chore_r.json()["id"]
        await authenticated_client.post(f"/v1/chores/{chore_id}/complete", json={})

        # Get testuser ID
        people_r = await authenticated_client.get("/v1/people")
        testuser = next((p for p in people_r.json() if p["username"] == "testuser"), None)
        assert testuser is not None
        person_id = testuser["id"]

        # Redeem points
        redeem_r = await authenticated_client.post(
            f"/v1/people/{person_id}/redeem",
            json={"amount": 25}
        )
        assert redeem_r.status_code == 200

        # Get history
        history_r = await authenticated_client.get(f"/v1/people/{person_id}/redemptions")
        assert history_r.status_code == 200
        redemptions = history_r.json()
        assert len(redemptions) == 1
        assert redemptions[0]["amount"] == 25
        assert redemptions[0]["person_id"] == person_id
        assert "redeemed_by" in redemptions[0]
        assert "timestamp" in redemptions[0]

    @pytest.mark.asyncio
    async def test_redemption_history_sorted_by_timestamp(self, authenticated_client):
        # Create and complete chore to earn points
        chore_r = await authenticated_client.post("/v1/chores", json={
            "name": "Test",
            "schedule_type": "interval",
            "schedule_config": {"days": 1},
            "points": 100
        })
        chore_id = chore_r.json()["id"]
        await authenticated_client.post(f"/v1/chores/{chore_id}/complete", json={})

        # Get testuser ID
        people_r = await authenticated_client.get("/v1/people")
        testuser = next((p for p in people_r.json() if p["username"] == "testuser"), None)
        assert testuser is not None
        person_id = testuser["id"]

        # Multiple redemptions
        await authenticated_client.post(f"/v1/people/{person_id}/redeem", json={"amount": 10})
        await authenticated_client.post(f"/v1/people/{person_id}/redeem", json={"amount": 20})
        await authenticated_client.post(f"/v1/people/{person_id}/redeem", json={"amount": 15})

        # Get history
        history_r = await authenticated_client.get(f"/v1/people/{person_id}/redemptions")
        redemptions = history_r.json()

        assert len(redemptions) == 3
        # Verify sorted by timestamp desc (newest first)
        timestamps = [r["timestamp"] for r in redemptions]
        assert timestamps == sorted(timestamps, reverse=True)


class TestChoresAPI:
    @pytest.mark.asyncio
    async def test_create_chore(self, authenticated_client):
        r = await authenticated_client.post("/v1/chores", json=WEEKLY_CHORE)
        assert r.status_code == 201
        data = r.json()
        assert data["name"] == "Vacuum"
        assert "id" in data
        assert isinstance(data["id"], int)
        assert data["schedule_summary"] == "Weekly on Mon"

    @pytest.mark.asyncio
    async def test_list_chores(self, authenticated_client):
        await authenticated_client.post("/v1/chores", json=WEEKLY_CHORE)
        r = await authenticated_client.get("/v1/chores")
        assert r.status_code == 200
        assert len(r.json()) == 1

    @pytest.mark.asyncio
    async def test_get_chore(self, authenticated_client):
        create_r = await authenticated_client.post("/v1/chores", json=WEEKLY_CHORE)
        chore_id = create_r.json()["id"]
        r = await authenticated_client.get(f"/v1/chores/{chore_id}")
        assert r.status_code == 200
        assert r.json()["name"] == "Vacuum"

    @pytest.mark.asyncio
    async def test_get_nonexistent(self, authenticated_client):
        r = await authenticated_client.get("/v1/chores/99999")
        assert r.status_code == 404

    @pytest.mark.asyncio
    async def test_duplicate_rejected(self, authenticated_client):
        await authenticated_client.post("/v1/chores", json=WEEKLY_CHORE)
        r = await authenticated_client.post("/v1/chores", json=WEEKLY_CHORE)
        assert r.status_code == 409

    @pytest.mark.asyncio
    async def test_update_chore(self, authenticated_client):
        create_r = await authenticated_client.post("/v1/chores", json=WEEKLY_CHORE)
        chore_id = create_r.json()["id"]
        r = await authenticated_client.put(f"/v1/chores/{chore_id}", json={"points": 10})
        assert r.status_code == 200
        assert r.json()["points"] == 10

    @pytest.mark.asyncio
    async def test_update_fixed_assignee_updates_current_assignee(self, authenticated_client):
        await authenticated_client.post("/v1/people", json={"name": "Alice", "username": "alice"})
        await authenticated_client.post("/v1/people", json={"name": "Bob", "username": "bob"})
        create_r = await authenticated_client.post(
            "/v1/chores",
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

        r = await authenticated_client.put(f"/v1/chores/{chore_id}", json={"assignee": "Bob"})
        assert r.status_code == 200
        data = r.json()
        assert data["assignee"] == "Bob"
        assert data["current_assignee"] == "Bob"

    @pytest.mark.asyncio
    async def test_update_rotating_current_and_next_assignee(self, authenticated_client):
        await authenticated_client.post("/v1/people", json={"name": "Alice", "username": "alice"})
        await authenticated_client.post("/v1/people", json={"name": "Bob", "username": "bob"})
        await authenticated_client.post("/v1/people", json={"name": "Carol", "username": "carol"})
        create_r = await authenticated_client.post(
            "/v1/chores",
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
            f"/v1/chores/{chore_id}",
            json={"current_assignee": "Bob", "next_assignee": "Carol"},
        )
        assert r.status_code == 200
        data = r.json()
        assert data["current_assignee"] == "Bob"
        assert data["next_assignee"] == "Carol"
        assert data["rotation_index"] == 1

    @pytest.mark.asyncio
    async def test_unassign_open_chore(self, authenticated_client):
        await authenticated_client.post("/v1/people", json={"name": "Alice", "username": "alice"})
        create_r = await authenticated_client.post(
            "/v1/chores",
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
            f"/v1/chores/{chore_id}",
            json={"current_assignee": "Alice"},
        )
        assert r.status_code == 200
        assert r.json()["current_assignee"] == "Alice"

        # Unassign (set to null)
        r = await authenticated_client.put(
            f"/v1/chores/{chore_id}",
            json={"current_assignee": None},
        )
        assert r.status_code == 200
        assert r.json()["current_assignee"] is None

        # Verify by fetching chore again
        r = await authenticated_client.get(f"/v1/chores/{chore_id}")
        assert r.status_code == 200
        assert r.json()["current_assignee"] is None

    @pytest.mark.asyncio
    async def test_update_next_due_from_past_to_future_resets_state_to_complete(self, authenticated_client):
        from datetime import date, timedelta

        # Create a chore (will have next_due calculated from schedule)
        create_r = await authenticated_client.post("/v1/chores", json=WEEKLY_CHORE)
        chore_id = create_r.json()["id"]
        initial_state = create_r.json()["state"]

        # Update next_due to a past date (should set state to "due")
        past_date = (date.today() - timedelta(days=1)).isoformat()
        r = await authenticated_client.put(f"/v1/chores/{chore_id}", json={"next_due": past_date})
        assert r.status_code == 200
        assert r.json()["state"] == "due"
        assert r.json()["next_due"] == past_date

        # Update next_due to a future date (should reset state to "complete")
        future_date = (date.today() + timedelta(days=5)).isoformat()
        r = await authenticated_client.put(f"/v1/chores/{chore_id}", json={"next_due": future_date})
        assert r.status_code == 200
        assert r.json()["state"] == "complete"
        assert r.json()["next_due"] == future_date

    @pytest.mark.asyncio
    async def test_update_next_due_to_today_sets_state_to_due(self, authenticated_client):
        from datetime import date, timedelta

        # Create a chore
        create_r = await authenticated_client.post("/v1/chores", json=WEEKLY_CHORE)
        chore_id = create_r.json()["id"]

        # First set to a future date
        future_date = (date.today() + timedelta(days=5)).isoformat()
        await authenticated_client.put(f"/v1/chores/{chore_id}", json={"next_due": future_date})

        # Update next_due to today (should set state to "due")
        today = date.today().isoformat()
        r = await authenticated_client.put(f"/v1/chores/{chore_id}", json={"next_due": today})
        assert r.status_code == 200
        assert r.json()["state"] == "due"
        assert r.json()["next_due"] == today

    @pytest.mark.asyncio
    async def test_update_next_due_back_to_future_resets_complete(self, authenticated_client):
        from datetime import date, timedelta

        # Create a chore
        create_r = await authenticated_client.post("/v1/chores", json=WEEKLY_CHORE)
        chore_id = create_r.json()["id"]

        # Set next_due to past date (state becomes "due")
        past_date = (date.today() - timedelta(days=2)).isoformat()
        r = await authenticated_client.put(f"/v1/chores/{chore_id}", json={"next_due": past_date})
        assert r.status_code == 200
        assert r.json()["state"] == "due"

        # Update next_due back to future (state should go back to "complete")
        future_date = (date.today() + timedelta(days=7)).isoformat()
        r = await authenticated_client.put(f"/v1/chores/{chore_id}", json={"next_due": future_date})
        assert r.status_code == 200
        assert r.json()["state"] == "complete"
        assert r.json()["next_due"] == future_date

    @pytest.mark.asyncio
    async def test_update_next_due_with_assignment_changes(self, authenticated_client):
        from datetime import date, timedelta

        # Set up people for assignment test
        await authenticated_client.post("/v1/people", json={"name": "Alice", "username": "alice"})
        await authenticated_client.post("/v1/people", json={"name": "Bob", "username": "bob"})

        # Create a fixed assignment chore
        create_r = await authenticated_client.post(
            "/v1/chores",
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
            f"/v1/chores/{chore_id}",
            json={"next_due": past_date, "assignee": "Bob"},
        )
        assert r.status_code == 200
        assert r.json()["state"] == "due"
        assert r.json()["next_due"] == past_date
        assert r.json()["assignee"] == "Bob"
        assert r.json()["current_assignee"] == "Bob"

        # Update to future date
        future_date = (date.today() + timedelta(days=5)).isoformat()
        r = await authenticated_client.put(f"/v1/chores/{chore_id}", json={"next_due": future_date})
        assert r.status_code == 200
        assert r.json()["state"] == "complete"
        assert r.json()["next_due"] == future_date
        assert r.json()["assignee"] == "Bob"

    @pytest.mark.asyncio
    async def test_delete_chore(self, authenticated_client):
        create_r = await authenticated_client.post("/v1/chores", json=WEEKLY_CHORE)
        chore_id = create_r.json()["id"]
        r = await authenticated_client.delete(f"/v1/chores/{chore_id}")
        assert r.status_code == 204

        r = await authenticated_client.get(f"/v1/chores/{chore_id}")
        assert r.status_code == 404

    @pytest.mark.asyncio
    async def test_complete_action(self, authenticated_client):
        r = await authenticated_client.post("/v1/chores", json=WEEKLY_CHORE)
        chore_id = r.json()["id"]

        # Force to due so we can complete it
        await authenticated_client.post(f"/v1/chores/{chore_id}/mark-due")
        r = await authenticated_client.post(f"/v1/chores/{chore_id}/complete", json={})
        assert r.status_code == 200
        assert r.json()["state"] == "complete"
        assert r.json()["last_completed_by"] == "testuser"

    @pytest.mark.asyncio
    async def test_complete_with_completed_by_uses_specified_person(self, authenticated_client):
        r = await authenticated_client.post("/v1/people", json={"name": "Alice", "username": "alice"})
        assert r.status_code == 201

        r = await authenticated_client.post("/v1/chores", json=WEEKLY_CHORE)
        chore_id = r.json()["id"]
        await authenticated_client.post(f"/v1/chores/{chore_id}/mark-due")

        # Complete with explicit completed_by — should credit alice, not testuser
        r = await authenticated_client.post(f"/v1/chores/{chore_id}/complete", json={"completed_by": "alice"})
        assert r.status_code == 200
        assert r.json()["last_completed_by"] == "alice"

    @pytest.mark.asyncio
    async def test_complete_without_completed_by_falls_back_to_auth_user(self, authenticated_client):
        r = await authenticated_client.post("/v1/chores", json=WEEKLY_CHORE)
        chore_id = r.json()["id"]
        await authenticated_client.post(f"/v1/chores/{chore_id}/mark-due")

        # No completed_by — falls back to current_user (testuser)
        r = await authenticated_client.post(f"/v1/chores/{chore_id}/complete", json={})
        assert r.status_code == 200
        assert r.json()["last_completed_by"] == "testuser"

    @pytest.mark.asyncio
    async def test_open_chore_clears_assignee_after_completion(self, authenticated_client):
        r = await authenticated_client.post("/v1/people", json={"name": "Alice", "username": "alice"})
        assert r.status_code == 201

        open_chore = {
            "name": "Open Chore",
            "schedule_type": "interval",
            "schedule_config": {"days": 7},
            "assignment_type": "open",
            "eligible_people": [],
            "points": 0,
        }
        r = await authenticated_client.post("/v1/chores", json=open_chore)
        chore_id = r.json()["id"]

        # Assign to an individual, then complete
        await authenticated_client.put(f"/v1/chores/{chore_id}", json={"current_assignee": "Alice"})
        await authenticated_client.post(f"/v1/chores/{chore_id}/mark-due")
        r = await authenticated_client.post(f"/v1/chores/{chore_id}/complete", json={})
        assert r.status_code == 200
        assert r.json()["current_assignee"] is None

        # Verify log still records who was assigned at completion time
        log_r = await authenticated_client.get(f"/v1/log?chore_id={chore_id}&action=completed")
        assert log_r.status_code == 200
        logs = log_r.json()
        assert len(logs) > 0
        assert logs[0]["assignee"] == "Alice"

    @pytest.mark.asyncio
    async def test_skip_action(self, authenticated_client):
        r = await authenticated_client.post("/v1/chores", json=WEEKLY_CHORE)
        chore_id = r.json()["id"]
        await authenticated_client.post(f"/v1/chores/{chore_id}/mark-due")

        r = await authenticated_client.post(f"/v1/chores/{chore_id}/skip")
        assert r.status_code == 200
        assert r.json()["state"] == "complete"
        assert r.json()["last_change_type"] == "skipped"

        # Verify ChoreLog has correct person (not "system")
        r = await authenticated_client.get(f"/v1/log?chore_id={chore_id}&action=skipped")
        assert r.status_code == 200
        logs = r.json()
        assert len(logs) > 0
        log_entry = logs[0]
        assert log_entry["person"] == "testuser"
        assert log_entry["action"] == "skipped"

    @pytest.mark.asyncio
    async def test_reassign_action(self, authenticated_client):
        await authenticated_client.post("/v1/people", json={"name": "Alice", "username": "alice"})
        await authenticated_client.post("/v1/people", json={"name": "Bob", "username": "bob"})
        r = await authenticated_client.post("/v1/chores", json=ROTATING_CHORE)
        chore_id = r.json()["id"]

        r = await authenticated_client.post(f"/v1/chores/{chore_id}/reassign", json={"assignee": "Bob"})
        assert r.status_code == 200
        assert r.json()["current_assignee"] == "Bob"

    @pytest.mark.asyncio
    async def test_mark_due_action(self, authenticated_client):
        r = await authenticated_client.post("/v1/chores", json=WEEKLY_CHORE)
        chore_id = r.json()["id"]
        await authenticated_client.post(f"/v1/chores/{chore_id}/complete", json={})

        r = await authenticated_client.post(f"/v1/chores/{chore_id}/mark-due")
        assert r.status_code == 200
        assert r.json()["state"] == "due"

    @pytest.mark.asyncio
    async def test_mark_due_action_updates_next_due_to_today(self, authenticated_client):
        from datetime import date, timedelta

        r = await authenticated_client.post("/v1/chores", json=WEEKLY_CHORE)
        chore_id = r.json()["id"]
        original_next_due = r.json()["next_due"]

        # Set next_due to future (use UTC-consistent date)
        from datetime import datetime, timezone as tz
        utc_today = datetime.now(tz.utc).date()
        future_date = (utc_today + timedelta(days=5)).isoformat()
        await authenticated_client.put(f"/v1/chores/{chore_id}", json={"next_due": future_date})

        # Mark due should set next_due to today
        r = await authenticated_client.post(f"/v1/chores/{chore_id}/mark-due")
        assert r.status_code == 200
        assert r.json()["state"] == "due"
        assert r.json()["next_due"] == utc_today.isoformat()

    @pytest.mark.asyncio
    async def test_skip_reassign_action(self, authenticated_client):
        await authenticated_client.post("/v1/people", json={"name": "Alice", "username": "alice"})
        await authenticated_client.post("/v1/people", json={"name": "Bob", "username": "bob"})
        r = await authenticated_client.post("/v1/chores", json=ROTATING_CHORE)
        chore_id = r.json()["id"]
        await authenticated_client.post(f"/v1/chores/{chore_id}/mark-due")

        r = await authenticated_client.post(f"/v1/chores/{chore_id}/skip-reassign", json={"assignee": "Bob"})
        assert r.status_code == 200
        data = r.json()
        assert data["state"] == "complete"
        assert data["current_assignee"] == "Bob"

        # Verify ChoreLog has correct person for skip action (not "system")
        r = await authenticated_client.get(f"/v1/log?chore_id={chore_id}&action=skipped")
        assert r.status_code == 200
        logs = r.json()
        assert len(logs) > 0
        skip_log = logs[0]
        assert skip_log["person"] == "testuser"
        assert skip_log["action"] == "skipped"

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
        r = await authenticated_client.post("/v1/chores", json=invalid_chore)
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
        r = await authenticated_client.post("/v1/chores", json=invalid_chore)
        assert r.status_code == 400


class TestPointsAPI:
    @pytest.mark.asyncio
    async def test_leaderboard_empty(self, authenticated_client):
        r = await authenticated_client.get("/v1/points")
        assert r.status_code == 200
        assert r.json() == []

    @pytest.mark.asyncio
    async def test_leaderboard_after_completion(self, authenticated_client):
        r = await authenticated_client.post("/v1/chores", json=WEEKLY_CHORE)
        chore_id = r.json()["id"]
        await authenticated_client.post(f"/v1/chores/{chore_id}/mark-due")
        await authenticated_client.post(f"/v1/chores/{chore_id}/complete", json={})

        r = await authenticated_client.get("/v1/points")
        assert r.status_code == 200
        data = r.json()
        assert len(data) == 1
        assert data[0]["person"] == "testuser"
        assert data[0]["total_points"] == 5

    @pytest.mark.asyncio
    async def test_person_history(self, authenticated_client):
        r = await authenticated_client.post("/v1/chores", json=WEEKLY_CHORE)
        chore_id = r.json()["id"]
        await authenticated_client.post(f"/v1/chores/{chore_id}/mark-due")
        await authenticated_client.post(f"/v1/chores/{chore_id}/complete", json={})

        r = await authenticated_client.get("/v1/points/testuser")
        assert r.status_code == 200
        data = r.json()
        assert len(data) == 1
        assert data[0]["points"] == 5

    @pytest.mark.asyncio
    async def test_points_summary_empty(self, authenticated_client):
        r = await authenticated_client.get("/v1/points/summary")
        assert r.status_code == 200
        # testuser created by authenticated_client fixture
        summary = r.json()
        assert len(summary) == 1
        assert summary[0]["person"] == "testuser"
        assert summary[0]["points_7d"] == 0
        assert summary[0]["points_30d"] == 0

    @pytest.mark.asyncio
    async def test_points_summary_includes_all_people(self, seeded_client):
        ac, db = seeded_client
        r = await ac.get("/v1/points/summary")
        assert r.status_code == 200
        names = [e["person"] for e in r.json()]
        assert "derek" in names
        assert "amy" in names
        assert "connor" in names
        assert "lucas" in names

    @pytest.mark.asyncio
    async def test_points_summary_counts_recent(self, seeded_client):
        ac, db = seeded_client
        # seeded_db provides derek: 10pts 3d ago (within 7d), 20pts 15d ago (within 30d only)
        r = await ac.get("/v1/points/summary")
        assert r.status_code == 200
        derek = next(e for e in r.json() if e["person"] == "derek")
        assert derek["points_7d"] == 10
        assert derek["points_30d"] == 30

    @pytest.mark.asyncio
    async def test_points_summary_zero_for_no_activity(self, seeded_client):
        ac, db = seeded_client
        # Amy has no PointsLog entries in seeded_db
        r = await ac.get("/v1/points/summary")
        assert r.status_code == 200
        amy = next(e for e in r.json() if e["person"] == "amy")
        assert amy["points_7d"] == 0
        assert amy["points_30d"] == 0

    @pytest.mark.asyncio
    async def test_user_stats_returns_nonzero_after_completion(self, seeded_client):
        """user_stats should return correct non-zero points_7d and points_30d using seeded data."""
        ac, db = seeded_client
        # seeded_db provides derek: 10pts 3d ago (within 7d), 20pts 15d ago (within 30d only)
        r = await ac.get("/v1/points/stats/derek")
        assert r.status_code == 200
        data = r.json()
        assert data["points_7d"] == 10
        assert data["points_30d"] == 30
        assert data["total_points"] == 30
        assert data["display_points"] == 30

    @pytest.mark.asyncio
    async def test_user_stats_excludes_old_entries(self, authenticated_client, db):
        """user_stats should exclude PointsLog entries older than the time window."""
        from datetime import datetime, timedelta, timezone
        from app.models import PointsLog

        # Insert a PointsLog entry with completed_at 40 days ago (outside both windows)
        old_entry = PointsLog(
            person="testuser",
            chore_id=0,
            points=99,
            completed_at=datetime.now(timezone.utc) - timedelta(days=40),
        )
        db.add(old_entry)
        await db.commit()

        r = await authenticated_client.get("/v1/points/stats/testuser")
        assert r.status_code == 200
        data = r.json()
        # Old entry should not appear in 7d or 30d windows
        assert data["points_7d"] == 0
        assert data["points_30d"] == 0
        # But total should include it
        assert data["total_points"] == 99

    @pytest.mark.asyncio
    async def test_user_stats_correct_totals_across_windows(self, authenticated_client, db):
        """user_stats should correctly bucket points into 7d vs 30d windows."""
        from datetime import datetime, timedelta, timezone
        from app.models import PointsLog

        # Entry within 7 days (also within 30 days)
        recent = PointsLog(
            person="testuser",
            chore_id=0,
            points=10,
            completed_at=datetime.now(timezone.utc) - timedelta(days=3),
        )
        # Entry within 30 days but outside 7 days
        older = PointsLog(
            person="testuser",
            chore_id=0,
            points=20,
            completed_at=datetime.now(timezone.utc) - timedelta(days=15),
        )
        db.add_all([recent, older])
        await db.commit()

        r = await authenticated_client.get("/v1/points/stats/testuser")
        assert r.status_code == 200
        data = r.json()
        assert data["points_7d"] == 10
        assert data["points_30d"] == 30
        assert data["total_points"] == 30

    @pytest.mark.asyncio
    async def test_health(self, authenticated_client):
        r = await authenticated_client.get("/health")
        assert r.status_code == 200
        assert r.json() == {"status": "ok"}


class TestLogAPI:
    @pytest.mark.asyncio
    async def test_log_filters_multiple_actions(self, authenticated_client):
        await authenticated_client.post("/v1/people", json={"name": "Alice", "username": "alice"})
        await authenticated_client.post("/v1/people", json={"name": "Bob", "username": "bob"})
        r = await authenticated_client.post("/v1/chores", json=ROTATING_CHORE)
        chore_id = r.json()["id"]

        await authenticated_client.post(f"/v1/chores/{chore_id}/mark-due")
        await authenticated_client.post(f"/v1/chores/{chore_id}/complete", json={})
        await authenticated_client.post(f"/v1/chores/{chore_id}/reassign", json={"assignee": "Bob"})
        await authenticated_client.put(f"/v1/chores/{chore_id}", json={"points": 9})

        # After fixing reassign_chore to record the requesting user, testuser is now
        # the actor for both completed and reassigned — both show up when filtering by testuser.
        r = await authenticated_client.get("/v1/log?person=testuser&actions=completed&actions=reassigned")
        assert r.status_code == 200
        actions = [entry["action"] for entry in r.json()]
        assert "completed" in actions
        assert "reassigned" in actions  # testuser is now correctly recorded (not "system")

        r = await authenticated_client.get("/v1/log?actions=completed&actions=reassigned")
        assert r.status_code == 200
        actions = [entry["action"] for entry in r.json()]
        assert "completed" in actions
        assert "reassigned" in actions
        assert "updated" not in actions

    @pytest.mark.asyncio
    async def test_complete_log_entry_has_assignee(self, authenticated_client):
        # Create people first so the rotating chore assignment is valid
        await authenticated_client.post("/v1/people", json={"name": "Alice", "username": "alice"})
        await authenticated_client.post("/v1/people", json={"name": "Bob", "username": "bob"})

        r = await authenticated_client.post("/v1/chores", json=ROTATING_CHORE)
        chore_id = r.json()["id"]

        await authenticated_client.post(f"/v1/chores/{chore_id}/mark-due")
        await authenticated_client.post(f"/v1/chores/{chore_id}/complete", json={})

        r = await authenticated_client.get(f"/v1/log?chore_id={chore_id}&action=completed")
        assert r.status_code == 200
        logs = r.json()
        assert len(logs) > 0
        entry = logs[0]
        assert "assignee" in entry
        # Rotating chore: assignee is the current_assignee before completion (Alice, index 0)
        assert entry["assignee"] == "Alice"

    @pytest.mark.asyncio
    async def test_complete_log_entry_assignee_null_for_open_chore(self, authenticated_client):
        r = await authenticated_client.post("/v1/chores", json=WEEKLY_CHORE)
        chore_id = r.json()["id"]

        await authenticated_client.post(f"/v1/chores/{chore_id}/mark-due")
        await authenticated_client.post(f"/v1/chores/{chore_id}/complete", json={})

        r = await authenticated_client.get(f"/v1/log?chore_id={chore_id}&action=completed")
        assert r.status_code == 200
        logs = r.json()
        assert len(logs) > 0
        entry = logs[0]
        assert "assignee" in entry
        # Open chore has no current_assignee, so assignee is null
        assert entry["assignee"] is None

    @pytest.mark.asyncio
    async def test_skip_log_entry_has_null_assignee(self, authenticated_client):
        r = await authenticated_client.post("/v1/chores", json=WEEKLY_CHORE)
        chore_id = r.json()["id"]

        await authenticated_client.post(f"/v1/chores/{chore_id}/mark-due")
        await authenticated_client.post(f"/v1/chores/{chore_id}/skip")

        r = await authenticated_client.get(f"/v1/log?chore_id={chore_id}&action=skipped")
        assert r.status_code == 200
        logs = r.json()
        assert len(logs) > 0
        entry = logs[0]
        assert "assignee" in entry
        assert entry["assignee"] is None

    @pytest.mark.asyncio
    async def test_reassign_log_entry_has_null_assignee(self, authenticated_client):
        await authenticated_client.post("/v1/people", json={"name": "Alice", "username": "alice"})
        r = await authenticated_client.post("/v1/chores", json=WEEKLY_CHORE)
        chore_id = r.json()["id"]

        await authenticated_client.post(f"/v1/chores/{chore_id}/reassign", json={"assignee": "Alice"})

        r = await authenticated_client.get(f"/v1/log?chore_id={chore_id}&action=reassigned")
        assert r.status_code == 200
        logs = r.json()
        assert len(logs) > 0
        entry = logs[0]
        assert "assignee" in entry
        assert entry["assignee"] is None


class TestUserLogAPI:
    @pytest.mark.asyncio
    async def test_goal_change_logged_in_unified_log(self, authenticated_client):
        r = await authenticated_client.post("/v1/people", json={"name": "Alice", "username": "alice"})
        person_id = r.json()["id"]

        r = await authenticated_client.put(f"/v1/people/{person_id}", json={"goal_7d": 30})
        assert r.status_code == 200

        r = await authenticated_client.get("/v1/log")
        assert r.status_code == 200
        logs = r.json()
        person_entries = [e for e in logs if e["chore_name"].startswith("Person:")]
        assert len(person_entries) >= 1
        goal_entry = next(
            (e for e in person_entries if e.get("field_name") == "goal_7d"),
            None,
        )
        assert goal_entry is not None
        assert goal_entry["old_value"] == "20"
        assert goal_entry["new_value"] == "30"
        assert goal_entry["action"] == "updated"

    @pytest.mark.asyncio
    async def test_goal_30d_change_logged(self, authenticated_client):
        r = await authenticated_client.post("/v1/people", json={"name": "Bob", "username": "bob"})
        person_id = r.json()["id"]

        await authenticated_client.put(f"/v1/people/{person_id}", json={"goal_30d": 100})

        r = await authenticated_client.get("/v1/log")
        logs = r.json()
        entry = next(
            (e for e in logs if e.get("field_name") == "goal_30d"),
            None,
        )
        assert entry is not None
        assert entry["old_value"] == "80"
        assert entry["new_value"] == "100"

    @pytest.mark.asyncio
    async def test_no_log_when_no_change(self, authenticated_client):
        r = await authenticated_client.post("/v1/people", json={"name": "Carol", "username": "carol"})
        person_id = r.json()["id"]

        # Send update with same value as default (goal_7d=20 already)
        await authenticated_client.put(f"/v1/people/{person_id}", json={"goal_7d": 20})

        r = await authenticated_client.get("/v1/log")
        logs = r.json()
        person_goal_entries = [
            e for e in logs
            if e["chore_name"].startswith("Person:") and e.get("field_name") == "goal_7d"
        ]
        assert len(person_goal_entries) == 0

    @pytest.mark.asyncio
    async def test_password_change_logged_to_auth_log(self, authenticated_client):
        """Admin password change should appear in auth_log, not user_log/chore_log."""
        r = await authenticated_client.post("/v1/people", json={"name": "Dave", "username": "dave"})
        person_id = r.json()["id"]

        await authenticated_client.put(f"/v1/people/{person_id}", json={"password": "newpassword123"})

        # Check auth log for password_changed event
        r = await authenticated_client.get("/v1/auth/log")
        auth_logs = r.json()
        pw_entries = [e for e in auth_logs if e.get("action") == "password_changed" and e.get("username") == "dave"]
        assert len(pw_entries) >= 1

        # Verify it does NOT appear in user_log (GET /log) as a field_name=password entry
        r = await authenticated_client.get("/v1/log")
        logs = r.json()
        pw_field_entries = [e for e in logs if e.get("field_name") == "password"]
        assert len(pw_field_entries) == 0

    @pytest.mark.asyncio
    async def test_person_log_uses_sentinel_chore_id(self, authenticated_client):
        r = await authenticated_client.post("/v1/people", json={"name": "Eve", "username": "eve"})
        person_id = r.json()["id"]
        await authenticated_client.put(f"/v1/people/{person_id}", json={"goal_7d": 25})

        r = await authenticated_client.get("/v1/log")
        logs = r.json()
        person_entries = [e for e in logs if e["chore_name"].startswith("Person:")]
        assert all(e["chore_id"] == 0 for e in person_entries)

    @pytest.mark.asyncio
    async def test_person_log_excluded_when_real_chore_id_filtered(self, authenticated_client):
        r = await authenticated_client.post("/v1/people", json={"name": "Frank", "username": "frank"})
        person_id = r.json()["id"]
        await authenticated_client.put(f"/v1/people/{person_id}", json={"goal_7d": 25})

        # Create a chore so we have a real chore_id to filter on
        r = await authenticated_client.post("/v1/chores", json=WEEKLY_CHORE)
        chore_id = r.json()["id"]

        r = await authenticated_client.get(f"/v1/log?chore_id={chore_id}")
        logs = r.json()
        person_entries = [e for e in logs if e["chore_name"].startswith("Person:")]
        assert len(person_entries) == 0

    @pytest.mark.asyncio
    async def test_unified_log_sorted_by_timestamp_desc(self, authenticated_client):
        r = await authenticated_client.post("/v1/people", json={"name": "Grace", "username": "grace"})
        person_id = r.json()["id"]

        r = await authenticated_client.post("/v1/chores", json=WEEKLY_CHORE)
        chore_id = r.json()["id"]
        await authenticated_client.post(f"/v1/chores/{chore_id}/mark-due")
        await authenticated_client.post(f"/v1/chores/{chore_id}/complete", json={})

        await authenticated_client.put(f"/v1/people/{person_id}", json={"goal_7d": 35})

        r = await authenticated_client.get("/v1/log")
        assert r.status_code == 200
        logs = r.json()
        timestamps = [e["timestamp"] for e in logs]
        assert timestamps == sorted(timestamps, reverse=True)

    @pytest.mark.asyncio
    async def test_skip_reassign_logs_reassignment(self, authenticated_client):
        await authenticated_client.post("/v1/people", json={"name": "Alice", "username": "alice"})
        await authenticated_client.post("/v1/people", json={"name": "Bob", "username": "bob"})
        r = await authenticated_client.post("/v1/chores", json=ROTATING_CHORE)
        chore_id = r.json()["id"]
        await authenticated_client.post(f"/v1/chores/{chore_id}/mark-due")

        r = await authenticated_client.post(
            f"/v1/chores/{chore_id}/skip-reassign", json={"assignee": "Bob"}
        )
        assert r.status_code == 200

        r = await authenticated_client.get(f"/v1/log?chore_id={chore_id}&action=reassigned")
        assert r.status_code == 200
        logs = r.json()
        assert len(logs) >= 1
        assert logs[0]["action"] == "reassigned"
        assert logs[0]["reassigned_to"] == "Bob"

    @pytest.mark.asyncio
    async def test_reassign_logs_requesting_user(self, authenticated_client):
        await authenticated_client.post("/v1/people", json={"name": "Alice", "username": "alice"})
        await authenticated_client.post("/v1/people", json={"name": "Bob", "username": "bob"})
        r = await authenticated_client.post("/v1/chores", json=ROTATING_CHORE)
        chore_id = r.json()["id"]
        await authenticated_client.post(f"/v1/chores/{chore_id}/mark-due")

        r = await authenticated_client.post(
            f"/v1/chores/{chore_id}/reassign", json={"assignee": "Bob"}
        )
        assert r.status_code == 200

        r = await authenticated_client.get(f"/v1/log?chore_id={chore_id}&action=reassigned")
        assert r.status_code == 200
        logs = r.json()
        assert len(logs) >= 1
        reassign_log = next(e for e in logs if e["action"] == "reassigned")
        # Should be the requesting user, not "system"
        assert reassign_log["person"] == "testuser"


