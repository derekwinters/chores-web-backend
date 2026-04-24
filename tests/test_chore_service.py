from datetime import date, datetime, timezone

import pytest

from app.models import Chore, PointsLog
from app.services.chore_service import (
    apply_assignment_state,
    complete_chore,
    compute_age,
    compute_next_assignee,
    compute_schedule_summary,
    mark_due_chore,
    reassign_chore,
    skip_and_reassign_chore,
    skip_chore,
    transition_overdue_chores,
    validate_assignment,
)


def _make_chore(**kwargs) -> Chore:
    defaults = dict(
        name="Test Chore",
        schedule_type="weekly",
        schedule_config={"days": [0]},
        assignment_type="open",
        eligible_people=[],
        points=0,
        state="due",
        rotation_index=0,
    )
    defaults.update(kwargs)
    return Chore(**defaults)


class TestComputeAge:
    def test_overdue(self):
        chore = _make_chore(next_due=date(2024, 1, 1))
        age = compute_age(chore)
        assert age > 0  # positive = overdue

    def test_no_due_date(self):
        chore = _make_chore(next_due=None)
        assert compute_age(chore) is None


class TestComputeScheduleSummary:
    def test_weekly(self):
        chore = _make_chore(schedule_type="weekly", schedule_config={"days": [0]})
        assert "Weekly" in compute_schedule_summary(chore)

    def test_interval(self):
        chore = _make_chore(schedule_type="interval", schedule_config={"days": 7})
        assert "Every 7 days" == compute_schedule_summary(chore)


class TestComputeNextAssignee:
    def test_rotating(self):
        chore = _make_chore(
            assignment_type="rotating",
            eligible_people=["Alice", "Bob", "Carol"],
            rotation_index=0,
        )
        assert compute_next_assignee(chore) == "Bob"

    def test_rotating_wraps(self):
        chore = _make_chore(
            assignment_type="rotating",
            eligible_people=["Alice", "Bob"],
            rotation_index=1,
        )
        assert compute_next_assignee(chore) == "Alice"

    def test_non_rotating_returns_none(self):
        chore = _make_chore(assignment_type="open")
        assert compute_next_assignee(chore) is None


class TestValidateAssignment:
    def test_open_assignment_always_valid(self):
        chore = _make_chore(assignment_type="open")
        assert validate_assignment(chore) is None

    def test_fixed_assignment_valid(self):
        chore = _make_chore(
            assignment_type="fixed",
            assignee="Alice",
            current_assignee="Alice",
        )
        assert validate_assignment(chore) is None

    def test_fixed_assignment_valid_on_creation(self):
        chore = _make_chore(
            assignment_type="fixed",
            assignee="Alice",
            current_assignee=None,
        )
        assert validate_assignment(chore) is None

    def test_fixed_assignment_mismatched_current(self):
        chore = _make_chore(
            assignment_type="fixed",
            assignee="Alice",
            current_assignee="Bob",
        )
        errors = validate_assignment(chore)
        assert errors is not None
        assert "current_assignee" in errors

    def test_fixed_assignment_missing_assignee(self):
        chore = _make_chore(
            assignment_type="fixed",
            assignee=None,
            current_assignee="Alice",
        )
        errors = validate_assignment(chore)
        assert errors is not None
        assert "assignee" in errors

    def test_rotating_assignment_valid(self):
        chore = _make_chore(
            assignment_type="rotating",
            eligible_people=["Alice", "Bob", "Carol"],
            current_assignee="Alice",
        )
        assert validate_assignment(chore) is None

    def test_rotating_assignment_invalid_current(self):
        chore = _make_chore(
            assignment_type="rotating",
            eligible_people=["Alice", "Bob"],
            current_assignee="Carol",
        )
        errors = validate_assignment(chore)
        assert errors is not None
        assert "current_assignee" in errors

    def test_rotating_assignment_invalid_next(self):
        chore = _make_chore(
            assignment_type="rotating",
            eligible_people=["Alice", "Bob"],
            current_assignee="Alice",
        )
        # Add next_assignee to dict representation for validation
        errors = validate_assignment({
            "assignment_type": "rotating",
            "eligible_people": ["Alice", "Bob"],
            "current_assignee": "Alice",
            "next_assignee": "Carol",
        })
        assert errors is not None
        assert "next_assignee" in errors

    def test_rotating_assignment_empty_eligible(self):
        chore = _make_chore(
            assignment_type="rotating",
            eligible_people=[],
            current_assignee=None,
        )
        errors = validate_assignment(chore)
        assert errors is not None
        assert "eligible_people" in errors

    def test_rotating_assignment_null_current_assignee(self):
        chore = _make_chore(
            assignment_type="rotating",
            eligible_people=["Alice", "Bob"],
            current_assignee=None,
        )
        assert validate_assignment(chore) is None

    def test_works_with_dict(self):
        chore_dict = {
            "assignment_type": "fixed",
            "assignee": "Alice",
            "current_assignee": "Alice",
            "eligible_people": [],
        }
        assert validate_assignment(chore_dict) is None

    def test_dict_invalid_fixed(self):
        chore_dict = {
            "assignment_type": "fixed",
            "assignee": "Alice",
            "current_assignee": "Bob",
            "eligible_people": [],
        }
        errors = validate_assignment(chore_dict)
        assert errors is not None
        assert "current_assignee" in errors


class TestApplyAssignmentState:
    def test_fixed_assignment_updates_current_assignee(self):
        chore = _make_chore(assignment_type="fixed", assignee="Alice", current_assignee="Alice")
        apply_assignment_state(chore, assignee="Bob")
        assert chore.assignee == "Bob"
        assert chore.current_assignee == "Bob"

    def test_rotating_next_assignee_recomputes_current(self):
        chore = _make_chore(
            assignment_type="rotating",
            eligible_people=["Alice", "Bob", "Carol"],
            current_assignee="Alice",
            rotation_index=0,
        )
        apply_assignment_state(chore, next_assignee="Alice")
        assert chore.current_assignee == "Carol"
        assert chore.rotation_index == 2


class TestCompleteChore:
    @pytest.mark.asyncio
    async def test_state_becomes_complete(self, db):
        chore = _make_chore(state="due", schedule_type="interval", schedule_config={"days": 7})
        db.add(chore)
        await db.commit()
        await db.refresh(chore)

        result = await complete_chore(chore, db)
        assert result.state == "complete"
        assert result.last_change_type == "completed"
        assert result.next_due is not None

    @pytest.mark.asyncio
    async def test_awards_points(self, db):
        chore = _make_chore(
            state="due", points=5,
            schedule_type="interval", schedule_config={"days": 7}
        )
        db.add(chore)
        await db.commit()
        await db.refresh(chore)

        await complete_chore(chore, db, completed_by="Alice")

        from sqlalchemy import select
        log = (await db.execute(select(PointsLog).where(PointsLog.person == "Alice"))).scalar_one()
        assert log.points == 5

    @pytest.mark.asyncio
    async def test_no_points_without_completer(self, db):
        chore = _make_chore(state="due", points=5, schedule_type="interval", schedule_config={"days": 7})
        db.add(chore)
        await db.commit()
        await db.refresh(chore)

        await complete_chore(chore, db, completed_by=None)

        from sqlalchemy import select
        logs = (await db.execute(select(PointsLog))).scalars().all()
        assert len(logs) == 0

    @pytest.mark.asyncio
    async def test_rotating_advances_assignee(self, db):
        chore = _make_chore(
            state="due",
            assignment_type="rotating",
            eligible_people=["Alice", "Bob"],
            current_assignee="Alice",
            rotation_index=0,
            schedule_type="interval",
            schedule_config={"days": 7},
        )
        db.add(chore)
        await db.commit()
        await db.refresh(chore)

        result = await complete_chore(chore, db)
        assert result.current_assignee == "Bob"
        assert result.rotation_index == 1


class TestSkipChore:
    @pytest.mark.asyncio
    async def test_skip_sets_complete(self, db):
        chore = _make_chore(state="due", schedule_type="interval", schedule_config={"days": 7})
        db.add(chore)
        await db.commit()
        await db.refresh(chore)

        result = await skip_chore(chore, db)
        assert result.state == "complete"
        assert result.last_change_type == "skipped"

    @pytest.mark.asyncio
    async def test_skip_does_not_award_points(self, db):
        chore = _make_chore(state="due", points=10, schedule_type="interval", schedule_config={"days": 7})
        db.add(chore)
        await db.commit()
        await db.refresh(chore)

        await skip_chore(chore, db)

        from sqlalchemy import select
        logs = (await db.execute(select(PointsLog))).scalars().all()
        assert len(logs) == 0


class TestReassignChore:
    @pytest.mark.asyncio
    async def test_reassign_changes_assignee(self, db):
        chore = _make_chore(
            state="due",
            assignment_type="rotating",
            eligible_people=["Alice", "Bob"],
            current_assignee="Alice",
            rotation_index=0,
        )
        db.add(chore)
        await db.commit()
        await db.refresh(chore)

        result = await reassign_chore(chore, db, assignee="Bob")
        assert result.current_assignee == "Bob"
        assert result.rotation_index == 1
        assert result.last_change_type == "reassigned"

    @pytest.mark.asyncio
    async def test_reassign_does_not_change_state(self, db):
        chore = _make_chore(state="due", current_assignee="Alice")
        db.add(chore)
        await db.commit()
        await db.refresh(chore)

        result = await reassign_chore(chore, db, assignee="Bob")
        assert result.state == "due"


class TestMarkDueChore:
    @pytest.mark.asyncio
    async def test_marks_complete_as_due(self, db):
        chore = _make_chore(state="complete")
        db.add(chore)
        await db.commit()
        await db.refresh(chore)

        result = await mark_due_chore(chore, db)
        assert result.state == "due"
        assert result.last_change_type == "marked_due"

    @pytest.mark.asyncio
    async def test_noop_when_already_due(self, db):
        chore = _make_chore(state="due")
        db.add(chore)
        await db.commit()
        await db.refresh(chore)

        result = await mark_due_chore(chore, db)
        assert result.state == "due"
        assert result.last_change_type is None


class TestTransitionOverdueChores:
    @pytest.mark.asyncio
    async def test_transitions_overdue(self, db):
        chore = _make_chore(state="complete", next_due=date(2020, 1, 1))
        db.add(chore)
        await db.commit()

        count = await transition_overdue_chores(db)
        assert count == 1

        await db.refresh(chore)
        assert chore.state == "due"

    @pytest.mark.asyncio
    async def test_skips_future(self, db):
        chore = _make_chore(state="complete", next_due=date(2099, 12, 31))
        db.add(chore)
        await db.commit()

        count = await transition_overdue_chores(db)
        assert count == 0
