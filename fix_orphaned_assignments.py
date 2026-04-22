"""Remove assignments to non-existent people from database."""
import asyncio
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.database import async_session_factory
from app.models import Chore, Person


async def fix_orphaned_assignments(db: AsyncSession) -> None:
    """Clean up assignments to non-existent people."""
    result = await db.execute(select(Person.name))
    existing_people = {row[0] for row in result.all()}

    # Fix current_assignee
    result = await db.execute(select(Chore).where(Chore.current_assignee.isnot(None)))
    chores = result.scalars().all()
    fixed_count = 0

    for chore in chores:
        if chore.current_assignee not in existing_people:
            print(f"Removing orphaned assignee '{chore.current_assignee}' from chore '{chore.name}'")
            chore.current_assignee = None
            fixed_count += 1

    # Fix eligible_people
    result = await db.execute(select(Chore))
    chores = result.scalars().all()

    for chore in chores:
        original = chore.eligible_people.copy() if chore.eligible_people else []
        chore.eligible_people = [p for p in (chore.eligible_people or []) if p in existing_people]
        if original != chore.eligible_people:
            removed = set(original) - set(chore.eligible_people)
            print(f"Removing orphaned eligible people {removed} from chore '{chore.name}'")
            fixed_count += 1

    if fixed_count > 0:
        await db.commit()
        print(f"\nFixed {fixed_count} chores with orphaned assignments")
    else:
        print("No orphaned assignments found")


async def main():
    async with async_session_factory() as db:
        await fix_orphaned_assignments(db)


if __name__ == "__main__":
    asyncio.run(main())
