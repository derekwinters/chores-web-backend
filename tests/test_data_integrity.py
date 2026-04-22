import pytest
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select

from app.models import Chore, Person


@pytest.mark.asyncio
async def test_no_orphaned_chore_assignments(seeded_db: AsyncSession):
    """Verify all chore assignments reference existing people"""
    result = await seeded_db.execute(select(Chore).where(Chore.current_assignee.isnot(None)))
    chores_with_assignees = result.scalars().all()

    result = await seeded_db.execute(select(Person))
    people = result.scalars().all()
    people_names = {p.name for p in people}

    for chore in chores_with_assignees:
        assert chore.current_assignee in people_names, (
            f"Chore '{chore.name}' assigned to non-existent person '{chore.current_assignee}'"
        )


@pytest.mark.asyncio
async def test_seed_data_has_users(seeded_db: AsyncSession):
    """Verify seed data includes at least one user"""
    result = await seeded_db.execute(select(Person))
    people = result.scalars().all()
    assert len(people) > 0, "No users in database - seed data may not have run"


@pytest.mark.asyncio
async def test_eligible_people_exist(seeded_db: AsyncSession):
    """Verify all eligible_people for chores exist in database"""
    result = await seeded_db.execute(select(Chore))
    chores = result.scalars().all()

    result = await seeded_db.execute(select(Person))
    people = result.scalars().all()
    people_names = {p.name for p in people}

    for chore in chores:
        for person in chore.eligible_people:
            assert person in people_names, (
                f"Chore '{chore.name}' has eligible person '{person}' who doesn't exist"
            )
