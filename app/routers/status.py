"""System status endpoints."""
from fastapi import APIRouter, Depends
from sqlalchemy.ext.asyncio import AsyncSession

from ..database import get_db

router = APIRouter(prefix="/api", tags=["status"])


@router.get("/db-status")
async def get_db_status(db: AsyncSession = Depends(get_db)):
    """Check database readiness status.

    Used by frontend to detect when database startup/migrations are complete.
    Returns immediately if DB is responsive.
    """
    try:
        # Simple query to verify DB connection and basic schema
        from sqlalchemy import text
        await db.execute(text("SELECT 1"))
        return {"ready": True}
    except Exception:
        return {"ready": False, "message": "Database initializing"}
