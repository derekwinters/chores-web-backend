"""System status endpoints."""
from fastapi import APIRouter
from pydantic import BaseModel

from ..database import get_db_status as get_db_status_func, get_migrations_in_progress

router = APIRouter(prefix="/status", tags=["status"])


class DBStatusResponse(BaseModel):
    """Database status response model."""
    status: str
    migrations_in_progress: bool


@router.get("/db-status", response_model=DBStatusResponse)
async def db_status():
    """Check database readiness status.

    Returns current database state (initializing/ready/error) and migration progress.
    Used by frontend to detect when database startup/migrations are complete.
    """
    status = get_db_status_func()
    return DBStatusResponse(
        status=status.value,
        migrations_in_progress=get_migrations_in_progress()
    )
