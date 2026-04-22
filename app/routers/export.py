from fastapi import APIRouter, Depends
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from ..database import get_db
from ..dependencies import get_current_user
from ..models import Person, Chore, Settings
from ..services.export_service import generate_export

router = APIRouter(
    prefix="/export",
    tags=["export"],
)


@router.get("/config", summary="Export configuration data")
async def export_config(
    current_user: str = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """
    Export configuration data (chores, people, settings).
    Does not include history logs or computed scores.
    """
    people_result = await db.execute(select(Person))
    people = people_result.scalars().all()

    chores_result = await db.execute(select(Chore))
    chores = chores_result.scalars().all()

    settings_result = await db.execute(select(Settings))
    settings = settings_result.scalars().all()

    return await generate_export(people, chores, settings)
