import logging
from datetime import datetime, timezone

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy import select, delete
from sqlalchemy.exc import IntegrityError
from sqlalchemy.ext.asyncio import AsyncSession

from ..database import get_db
from ..models import Person, RedemptionLog
from ..schemas import PersonCreate, PersonOut, PersonUpdate, PersonRedemption, RedemptionLogOut
from ..dependencies import get_current_user, require_admin
from ..security import hash_password
from ..services.logging import log_person_change, log_auth_event

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/people", tags=["people"])


@router.get("", response_model=list[PersonOut])
async def list_people(current_user: str = Depends(get_current_user), db: AsyncSession = Depends(get_db)):
    result = await db.execute(select(Person).order_by(Person.name))
    return result.scalars().all()


@router.post("", response_model=PersonOut, status_code=201)
async def create_person(body: PersonCreate, current_user: str = Depends(require_admin), db: AsyncSession = Depends(get_db)):
    existing_name = await db.execute(select(Person).where(Person.name == body.name))
    if existing_name.scalar_one_or_none():
        raise HTTPException(status_code=409, detail="Person already exists")

    existing_username = await db.execute(select(Person).where(Person.username == body.username))
    if existing_username.scalar_one_or_none():
        raise HTTPException(status_code=409, detail="Username already exists")

    person = Person(
        name=body.name,
        username=body.username,
        password_hash=hash_password(body.password or ""),
        is_admin=False,
        requires_password_reset=False,
        color=body.color or "#3B82F6"  # TODO: Remove color field in next major version
    )
    db.add(person)
    await log_auth_event(body.username, "user_created", db, changed_by=current_user)
    try:
        await db.commit()
        await db.refresh(person)
    except IntegrityError as e:
        await db.rollback()
        if e.orig and "UniqueViolationError" in type(e.orig).__name__:
            logger.warning("Person '%s' or username '%s' already exists", body.name, body.username)
            raise HTTPException(status_code=409, detail="Person already exists")
        logger.exception("Unexpected integrity error creating person '%s'", body.name)
        raise HTTPException(status_code=500, detail="Database error while creating person")
    except Exception:
        await db.rollback()
        logger.exception("Unexpected error creating person '%s'", body.name)
        raise
    return person


@router.put("/{person_id}", response_model=PersonOut)
async def update_person(person_id: int, body: PersonUpdate, current_user: str = Depends(require_admin), db: AsyncSession = Depends(get_db)):
    result = await db.execute(select(Person).where(Person.id == person_id))
    person = result.scalar_one_or_none()
    if not person:
        raise HTTPException(status_code=404, detail="Person not found")

    # Check if new username is already taken
    if body.username and body.username != person.username:
        existing = await db.execute(select(Person).where(Person.username == body.username))
        if existing.scalar_one_or_none():
            raise HTTPException(status_code=409, detail="Username already exists")

    # Loggable fields: capture old values before mutation
    loggable_fields = ["name", "username", "color", "goal_7d", "goal_30d", "is_admin", "preferred_theme"]  # TODO: Remove color field in next major version
    old_values = {f: getattr(person, f) for f in loggable_fields}

    updates = {
        "name": body.name,
        "username": body.username,
        "color": body.color,
        "goal_7d": body.goal_7d,
        "goal_30d": body.goal_30d,
        "is_admin": body.is_admin,
        "preferred_theme": body.preferred_theme,
    }

    for field, value in updates.items():
        if value is not None:
            setattr(person, field, value)

    if body.password:
        person.password_hash = hash_password(body.password)
        # When admin changes another user's password, require them to reset it on next login
        if current_user != person.username:
            person.requires_password_reset = True
        # Log to auth_log (auth event) instead of user_log
        await log_auth_event(person.username, "password_changed", db, changed_by=current_user)

    # Log each changed loggable field
    for field in loggable_fields:
        new_val = getattr(person, field)
        old_val = old_values[field]
        if old_val != new_val:
            await log_person_change(
                person_id=person.id,
                person_name=person.name,
                action="updated",
                changed_by=current_user,
                db=db,
                field_name=field,
                old_value=None if old_val is None else str(old_val),
                new_value=None if new_val is None else str(new_val),
            )

    try:
        await db.commit()
        await db.refresh(person)
    except IntegrityError as e:
        await db.rollback()
        if e.orig and "UniqueViolationError" in type(e.orig).__name__:
            logger.warning("Unique constraint violation updating person id=%s", person_id)
            raise HTTPException(status_code=409, detail="Username already exists")
        logger.exception("Unexpected integrity error updating person id=%s", person_id)
        raise HTTPException(status_code=500, detail="Database error while updating person")
    except Exception:
        await db.rollback()
        logger.exception("Unexpected error updating person id=%s", person_id)
        raise
    return person


@router.delete("/{person_id}", status_code=204)
async def delete_person(person_id: int, current_user: str = Depends(require_admin), db: AsyncSession = Depends(get_db)):
    result = await db.execute(select(Person).where(Person.id == person_id))
    person = result.scalar_one_or_none()
    if not person:
        raise HTTPException(status_code=404, detail="Person not found")
    await db.delete(person)
    try:
        await db.commit()
    except IntegrityError as e:
        await db.rollback()
        if e.orig and "UniqueViolationError" in type(e.orig).__name__:
            logger.warning("Unique constraint violation deleting person id=%s", person_id)
            raise HTTPException(status_code=409, detail="Conflict deleting person")
        logger.exception("Unexpected integrity error deleting person id=%s", person_id)
        raise HTTPException(status_code=500, detail="Database error while deleting person")
    except Exception:
        await db.rollback()
        logger.exception("Unexpected error deleting person id=%s", person_id)
        raise


@router.post("/{person_id}/redeem", response_model=PersonOut)
async def redeem_points(person_id: int, body: PersonRedemption, current_user: str = Depends(require_admin), db: AsyncSession = Depends(get_db)):
    from ..models import PointsLog

    result = await db.execute(select(Person).where(Person.id == person_id))
    person = result.scalar_one_or_none()
    if not person:
        raise HTTPException(status_code=404, detail="Person not found")

    if body.amount <= 0:
        raise HTTPException(status_code=400, detail="Redemption amount must be positive")

    # Calculate total points from PointsLog (same as stats endpoint)
    points_result = await db.execute(select(PointsLog).where(PointsLog.person == person.username))
    logs = points_result.scalars().all()
    total_points = sum(log.points for log in logs)

    available_points = total_points - person.points_redeemed
    if body.amount > available_points:
        raise HTTPException(status_code=400, detail=f"Insufficient points. Available: {available_points}")

    person.points_redeemed += body.amount
    redemption = RedemptionLog(
        person_id=person_id,
        amount=body.amount,
        redeemed_by=current_user,
        timestamp=datetime.now(timezone.utc)
    )
    db.add(redemption)
    try:
        await db.commit()
        await db.refresh(person)
    except IntegrityError as e:
        await db.rollback()
        if e.orig and "UniqueViolationError" in type(e.orig).__name__:
            logger.warning("Unique constraint violation redeeming points for person id=%s", person_id)
            raise HTTPException(status_code=409, detail="Conflict redeeming points")
        logger.exception("Unexpected integrity error redeeming points for person id=%s", person_id)
        raise HTTPException(status_code=500, detail="Database error while redeeming points")
    except Exception:
        await db.rollback()
        logger.exception("Unexpected error redeeming points for person id=%s", person_id)
        raise
    return person


@router.get("/{person_id}/redemptions", response_model=list[RedemptionLogOut])
async def get_redemption_history(person_id: int, current_user: str = Depends(get_current_user), db: AsyncSession = Depends(get_db)):
    result = await db.execute(select(Person).where(Person.id == person_id))
    person = result.scalar_one_or_none()
    if not person:
        raise HTTPException(status_code=404, detail="Person not found")

    redemptions_result = await db.execute(
        select(RedemptionLog)
        .where(RedemptionLog.person_id == person_id)
        .order_by(RedemptionLog.timestamp.desc())
    )
    return redemptions_result.scalars().all()
