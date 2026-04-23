from __future__ import annotations

import json
import re
from datetime import date
from typing import Optional

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from ..database import get_db
from ..models import Chore, Person
from ..schemas import (
    ChoreCreate,
    ChoreOut,
    ChoreUpdate,
    CompleteBody,
    ReassignBody,
    SkipReassignBody,
)
from ..services.chore_service import (
    apply_assignment_state,
    complete_chore,
    compute_age,
    compute_next_assignee,
    compute_schedule_summary,
    initialize_chore,
    mark_due_chore,
    reassign_chore,
    skip_and_reassign_chore,
    skip_chore,
)
from ..services.logging import log_chore_change
from ..dependencies import get_current_user

router = APIRouter(
    prefix="/chores",
    tags=["chores"],
    responses={
        404: {"description": "Chore not found"},
        401: {"description": "Not authenticated"},
    },
)


def _slugify(name: str) -> str:
    return re.sub(r"[^a-z0-9]+", "_", name.lower()).strip("_")


def _enrich(chore: Chore) -> ChoreOut:
    out = ChoreOut.model_validate(chore)
    out.age = compute_age(chore)
    out.schedule_summary = compute_schedule_summary(chore)
    out.next_assignee = compute_next_assignee(chore)
    return out


async def _get_or_404(chore_id: int, db: AsyncSession) -> Chore:
    result = await db.execute(select(Chore).where(Chore.id == chore_id))
    chore = result.scalar_one_or_none()
    if not chore:
        raise HTTPException(status_code=404, detail="Chore not found")
    return chore


async def _validate_people_exist(db: AsyncSession, people: list[str] | None, assignee: str | None) -> None:
    if not people and not assignee:
        return

    result = await db.execute(select(Person.name))
    existing_names = {row[0] for row in result.all()}

    if assignee and assignee not in existing_names:
        raise HTTPException(status_code=400, detail=f"Person '{assignee}' does not exist")

    if people:
        invalid = [p for p in people if p not in existing_names]
        if invalid:
            raise HTTPException(status_code=400, detail=f"People do not exist: {', '.join(invalid)}")


def _validate_assignment_state(
    *,
    assignment_type: str,
    eligible_people: list[str],
    assignee: str | None,
    current_assignee: str | None,
    next_assignee: str | None,
) -> None:
    if assignment_type == "fixed":
        if current_assignee and assignee and current_assignee != assignee:
            raise HTTPException(status_code=400, detail="Fixed chores must have matching assignee and current_assignee")
        return

    if assignment_type == "rotating":
        if not eligible_people:
            raise HTTPException(status_code=400, detail="Rotating chores require eligible people")
        if current_assignee and current_assignee not in eligible_people:
            raise HTTPException(status_code=400, detail="Current assignee must be in eligible_people")
        if next_assignee and next_assignee not in eligible_people:
            raise HTTPException(status_code=400, detail="Next assignee must be in eligible_people")
        if current_assignee and next_assignee:
            current_idx = eligible_people.index(current_assignee)
            expected_next = eligible_people[(current_idx + 1) % len(eligible_people)]
            if expected_next != next_assignee:
                raise HTTPException(status_code=400, detail="Next assignee must immediately follow current assignee in the rotation")
        return

    if next_assignee:
        raise HTTPException(status_code=400, detail="Only rotating chores can set next_assignee")


@router.get("", response_model=list[ChoreOut], summary="List all chores")
async def list_chores(
    current_user: str = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """
    Get all chores.

    Returns a list of all chores with computed fields:
    - age: days overdue (negative = future due date)
    - schedule_summary: human-readable schedule description
    - next_assignee: next person in rotation (for rotating chores)
    """
    result = await db.execute(select(Chore).order_by(Chore.name))
    return [_enrich(c) for c in result.scalars().all()]


@router.get("/{chore_id}", response_model=ChoreOut, summary="Get a specific chore")
async def get_chore(
    chore_id: int,
    current_user: str = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """Get a single chore by ID."""
    return _enrich(await _get_or_404(chore_id, db))


@router.post("", response_model=ChoreOut, status_code=201)
async def create_chore(body: ChoreCreate, current_user: str = Depends(get_current_user), db: AsyncSession = Depends(get_db)):
    await _validate_people_exist(db, body.eligible_people, body.assignee)

    # Check for duplicate chore name
    existing = await db.execute(select(Chore).where(Chore.name == body.name))
    if existing.scalar_one_or_none():
        raise HTTPException(status_code=409, detail="Chore with that name already exists")

    chore = Chore(
        name=body.name,
        schedule_type=body.schedule_type,
        schedule_config=body.schedule_config,
        assignment_type=body.assignment_type,
        eligible_people=body.eligible_people,
        assignee=body.assignee,
        points=body.points,
    )
    await initialize_chore(chore, db)
    await db.flush()
    await log_chore_change(
        chore_id=chore.id,
        chore_name=chore.name,
        action="created",
        person=current_user,
        db=db,
    )
    await db.commit()
    return _enrich(chore)


@router.put("/{chore_id}", response_model=ChoreOut)
async def update_chore(chore_id: int, body: ChoreUpdate, current_user: str = Depends(get_current_user), db: AsyncSession = Depends(get_db)):
    chore = await _get_or_404(chore_id, db)
    updates = body.model_dump(exclude_none=True)
    current_assignee = updates.pop("current_assignee", None)
    next_assignee = updates.pop("next_assignee", None)
    target_assignment_type = updates.get("assignment_type", chore.assignment_type)
    target_eligible_people = updates.get("eligible_people", chore.eligible_people)
    target_assignee = updates.get("assignee", chore.assignee)
    target_current_assignee = current_assignee if current_assignee is not None else chore.current_assignee

    if target_assignment_type == "fixed" and updates.get("assignee") is not None and current_assignee is None:
        target_current_assignee = updates["assignee"]

    people_to_validate = updates.get("eligible_people")
    assignee_to_validate = updates.get("assignee")
    extra_people = [name for name in [current_assignee, next_assignee] if name is not None]
    if extra_people:
        people_to_validate = list(dict.fromkeys((people_to_validate or []) + extra_people))

    await _validate_people_exist(db, people_to_validate, assignee_to_validate)
    _validate_assignment_state(
        assignment_type=target_assignment_type,
        eligible_people=target_eligible_people or [],
        assignee=target_assignee,
        current_assignee=target_current_assignee,
        next_assignee=next_assignee,
    )

    for field, value in updates.items():
        old_value = getattr(chore, field, None)

        # Convert complex types to JSON for logging
        old_str = None
        new_str = None
        if old_value is not None:
            old_str = json.dumps(old_value) if isinstance(old_value, (dict, list)) else str(old_value)
        if value is not None:
            new_str = json.dumps(value) if isinstance(value, (dict, list)) else str(value)

        # Only log if value actually changed
        if old_value != value:
            await log_chore_change(
                chore_id=chore.id,
                chore_name=chore.name,
                action="updated",
                person=current_user,
                db=db,
                field_name=field,
                old_value=old_str,
                new_value=new_str,
            )

        setattr(chore, field, value)

    if target_assignment_type == "fixed" and updates.get("assignee") is not None and current_assignee is None:
        current_assignee = updates["assignee"]

    if current_assignee is not None or next_assignee is not None or any(
        key in updates for key in ("assignment_type", "eligible_people", "assignee")
    ):
        old_current = chore.current_assignee
        old_next = compute_next_assignee(chore)
        old_rotation_index = chore.rotation_index

        apply_assignment_state(
            chore,
            assignment_type=target_assignment_type,
            eligible_people=target_eligible_people,
            assignee=target_assignee,
            current_assignee=current_assignee,
            next_assignee=next_assignee,
        )

        assignment_changes = []
        if chore.current_assignee != old_current:
            assignment_changes.append(("current_assignee", old_current, chore.current_assignee))
        if compute_next_assignee(chore) != old_next:
            assignment_changes.append(("next_assignee", old_next, compute_next_assignee(chore)))
        if chore.rotation_index != old_rotation_index:
            assignment_changes.append(("rotation_index", old_rotation_index, chore.rotation_index))

        for field_name, old_value, new_value in assignment_changes:
            await log_chore_change(
                chore_id=chore.id,
                chore_name=chore.name,
                action="updated",
                person=current_user,
                db=db,
                field_name=field_name,
                old_value=None if old_value is None else str(old_value),
                new_value=None if new_value is None else str(new_value),
            )

    db.add(chore)
    await db.commit()
    await db.refresh(chore)
    return _enrich(chore)


@router.delete("/{chore_id}", status_code=204)
async def delete_chore(chore_id: int, current_user: str = Depends(get_current_user), db: AsyncSession = Depends(get_db)):
    chore = await _get_or_404(chore_id, db)
    await log_chore_change(
        chore_id=chore.id,
        chore_name=chore.name,
        action="deleted",
        person=current_user,
        db=db,
    )
    await db.delete(chore)
    await db.commit()


@router.post("/{chore_id}/complete", response_model=ChoreOut)
async def action_complete(chore_id: int, body: CompleteBody, current_user: str = Depends(get_current_user), db: AsyncSession = Depends(get_db)):
    chore = await _get_or_404(chore_id, db)
    return _enrich(await complete_chore(chore, db, completed_by=body.completed_by))


@router.post("/{chore_id}/skip", response_model=ChoreOut)
async def action_skip(chore_id: int, current_user: str = Depends(get_current_user), db: AsyncSession = Depends(get_db)):
    chore = await _get_or_404(chore_id, db)
    return _enrich(await skip_chore(chore, db))


@router.post("/{chore_id}/skip-reassign", response_model=ChoreOut)
async def action_skip_reassign(chore_id: int, body: SkipReassignBody, current_user: str = Depends(get_current_user), db: AsyncSession = Depends(get_db)):
    await _validate_people_exist(db, None, body.assignee)
    chore = await _get_or_404(chore_id, db)
    return _enrich(await skip_and_reassign_chore(chore, db, assignee=body.assignee))


@router.post("/{chore_id}/reassign", response_model=ChoreOut)
async def action_reassign(chore_id: int, body: ReassignBody, current_user: str = Depends(get_current_user), db: AsyncSession = Depends(get_db)):
    await _validate_people_exist(db, None, body.assignee)
    chore = await _get_or_404(chore_id, db)
    return _enrich(await reassign_chore(chore, db, assignee=body.assignee))


@router.post("/{chore_id}/mark-due", response_model=ChoreOut)
async def action_mark_due(chore_id: int, current_user: str = Depends(get_current_user), db: AsyncSession = Depends(get_db)):
    chore = await _get_or_404(chore_id, db)
    return _enrich(await mark_due_chore(chore, db))
