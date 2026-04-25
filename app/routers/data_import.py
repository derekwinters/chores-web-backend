from fastapi import APIRouter, Depends
from sqlalchemy.ext.asyncio import AsyncSession

from ..database import get_db
from ..dependencies import get_current_user
from ..services.import_service import import_config

router = APIRouter(
    prefix="/import",
    tags=["import"],
)


@router.post("/config", summary="Import configuration data")
async def import_config_endpoint(
    data: dict,
    current_user: str = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """
    Import configuration data (people, chores, settings).
    Uses replace strategy: clears existing data and imports from backup.
    """
    result = await import_config(data, db)
    return result
