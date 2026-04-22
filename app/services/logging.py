import logging
import json
from datetime import datetime, timezone
from sqlalchemy.ext.asyncio import AsyncSession
from ..models import ChoreLog

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
