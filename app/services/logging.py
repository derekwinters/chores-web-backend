import logging
import json
from datetime import datetime, timezone
from sqlalchemy.ext.asyncio import AsyncSession
from ..models import ChoreLog, UserLog

logger = logging.getLogger(__name__)


async def log_chore_change(
    chore_id: int,
    chore_name: str,
    action: str,
    person: str,
    db: AsyncSession,
    field_name: str | None = None,
    old_value: str | None = None,
    new_value: str | None = None,
    reassigned_to: str | None = None,
) -> None:
    """Log a chore action or field change."""
    timestamp = datetime.now(timezone.utc)

    log_entry = {
        "timestamp": timestamp.isoformat(),
        "chore_id": chore_id,
        "chore_name": chore_name,
        "action": action,
        "person": person,
    }

    if field_name is not None:
        log_entry["field_name"] = field_name
    if old_value is not None:
        log_entry["old_value"] = old_value
    if new_value is not None:
        log_entry["new_value"] = new_value
    if reassigned_to is not None:
        log_entry["reassigned_to"] = reassigned_to

    logger.info(json.dumps(log_entry))

    log = ChoreLog(
        chore_id=chore_id,
        chore_name=chore_name,
        person=person,
        action=action,
        timestamp=timestamp,
        field_name=field_name,
        old_value=old_value,
        new_value=new_value,
        reassigned_to=reassigned_to,
    )
    db.add(log)


# Fields whose values must not be stored in plaintext
_MASKED_FIELDS = {"password", "password_hash"}


async def log_person_change(
    person_id: int,
    person_name: str,
    action: str,
    changed_by: str,
    db: AsyncSession,
    field_name: str | None = None,
    old_value: str | None = None,
    new_value: str | None = None,
) -> None:
    """Log a person field change or action."""
    timestamp = datetime.now(timezone.utc)

    # Mask sensitive fields
    if field_name in _MASKED_FIELDS:
        old_value = "changed" if old_value is not None else None
        new_value = "changed" if new_value is not None else None

    log_entry: dict = {
        "timestamp": timestamp.isoformat(),
        "person_id": person_id,
        "person_name": person_name,
        "action": action,
        "changed_by": changed_by,
    }

    if field_name is not None:
        log_entry["field_name"] = field_name
    if old_value is not None:
        log_entry["old_value"] = old_value
    if new_value is not None:
        log_entry["new_value"] = new_value

    logger.info(json.dumps(log_entry))

    log = UserLog(
        person_id=person_id,
        person_name=person_name,
        action=action,
        field_name=field_name,
        old_value=old_value,
        new_value=new_value,
        changed_by=changed_by,
        timestamp=timestamp,
    )
    db.add(log)
