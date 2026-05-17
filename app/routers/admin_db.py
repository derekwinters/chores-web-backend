from datetime import datetime, timezone

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy import func, or_, select
from sqlalchemy.ext.asyncio import AsyncSession

from ..database import get_db
from ..dependencies import require_admin
from ..models import ChoreLog, Person, PointsLog
from ..schemas import AdminDbPage, PointsLogAdminOut, PointsLogUpdate

router = APIRouter(prefix="/admin/db", tags=["admin-db"])


@router.get("/points-log", response_model=AdminDbPage)
async def list_points_log(
    limit: int = 20,
    offset: int = 0,
    current_admin: str = Depends(require_admin),
    db: AsyncSession = Depends(get_db),
):
    """Paginated list of PointsLog rows, newest first."""
    total_result = await db.execute(select(func.count()).select_from(PointsLog))
    total = total_result.scalar_one()

    rows_result = await db.execute(
        select(PointsLog)
        .order_by(PointsLog.completed_at.desc())
        .limit(limit)
        .offset(offset)
    )
    items = rows_result.scalars().all()

    return AdminDbPage(
        items=[PointsLogAdminOut.model_validate(row) for row in items],
        total=total,
        offset=offset,
        limit=limit,
    )


@router.patch("/points-log/{entry_id}", response_model=PointsLogAdminOut)
async def update_points_log(
    entry_id: int,
    body: PointsLogUpdate,
    current_admin: str = Depends(require_admin),
    db: AsyncSession = Depends(get_db),
):
    """Edit points and/or person on a PointsLog row.

    Computes the delta and applies it to Person.points.
    Writes a ChoreLog audit entry.
    """
    row_result = await db.execute(select(PointsLog).where(PointsLog.id == entry_id))
    row = row_result.scalar_one_or_none()
    if row is None:
        raise HTTPException(status_code=404, detail="PointsLog entry not found")

    old_points = row.points
    old_person_name = row.person

    def _person_lookup(name: str):
        """Match by username or display name — handles legacy rows that stored display name."""
        return or_(Person.username == name, Person.name == name)

    if body.person == old_person_name:
        # Same person — apply delta only
        delta = body.points - old_points
        if delta != 0:
            person_result = await db.execute(
                select(Person).where(_person_lookup(old_person_name))
            )
            person_obj = person_result.scalar_one_or_none()
            if person_obj is not None:
                person_obj.points = max(0, person_obj.points + delta)
    else:
        # Person changed — rebalance both sides (no delta block to avoid double-adjustment)
        old_person_result = await db.execute(
            select(Person).where(_person_lookup(old_person_name))
        )
        old_person_obj = old_person_result.scalar_one_or_none()
        if old_person_obj is not None:
            old_person_obj.points = max(0, old_person_obj.points - old_points)

        new_person_result = await db.execute(
            select(Person).where(_person_lookup(body.person))
        )
        new_person_obj = new_person_result.scalar_one_or_none()
        if new_person_obj is not None:
            new_person_obj.points = max(0, new_person_obj.points + body.points)

    # --- audit log ---
    changes = []
    if old_points != body.points:
        changes.append(f"points: {old_points} -> {body.points}")
    if old_person_name != body.person:
        changes.append(f"person: {old_person_name} -> {body.person}")

    audit = ChoreLog(
        chore_id=row.chore_id,
        chore_name=f"PointsLog#{entry_id}",
        person=current_admin,
        action="admin_edit",
        timestamp=datetime.now(timezone.utc),
        field_name="points_log",
        old_value=f"points={old_points}, person={old_person_name}",
        new_value=f"points={body.points}, person={body.person}",
    )
    db.add(audit)

    # --- update the row ---
    row.points = body.points
    row.person = body.person

    await db.commit()
    await db.refresh(row)
    return PointsLogAdminOut.model_validate(row)


@router.delete("/points-log/{entry_id}", status_code=204)
async def delete_points_log(
    entry_id: int,
    current_admin: str = Depends(require_admin),
    db: AsyncSession = Depends(get_db),
):
    """Delete a PointsLog row.

    Reverses points on Person (floor at 0).
    Writes a ChoreLog audit entry.
    """
    row_result = await db.execute(select(PointsLog).where(PointsLog.id == entry_id))
    row = row_result.scalar_one_or_none()
    if row is None:
        raise HTTPException(status_code=404, detail="PointsLog entry not found")

    # Reverse points on person (floor at 0)
    person_result = await db.execute(
        select(Person).where(or_(Person.username == row.person, Person.name == row.person))
    )
    person_obj = person_result.scalar_one_or_none()
    if person_obj is not None:
        person_obj.points = max(0, person_obj.points - row.points)

    # Audit log
    audit = ChoreLog(
        chore_id=row.chore_id,
        chore_name=f"PointsLog#{entry_id}",
        person=current_admin,
        action="admin_delete",
        timestamp=datetime.now(timezone.utc),
        field_name="points_log",
        old_value=f"points={row.points}, person={row.person}",
        new_value=None,
    )
    db.add(audit)

    await db.delete(row)
    await db.commit()
