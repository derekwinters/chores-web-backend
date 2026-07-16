"""System status endpoints."""
from fastapi import APIRouter
from pydantic import BaseModel

from ..config import APP_VERSION, API_VERSION, SUPPORTED_API_VERSIONS
from ..database import get_db_status as get_db_status_func, get_migrations_in_progress

router = APIRouter(prefix="/status", tags=["status"])


class StatusResponse(BaseModel):
    """Backend + API version status response model.

    Served on the unversioned /status/ endpoint so clients can read the
    running backend version and negotiate the API major version deliberately
    before choosing a versioned (/v1/...) path.
    """
    version: str
    api_version: str
    versions: list[str]


class DBStatusResponse(BaseModel):
    """Database status response model."""
    status: str
    migrations_in_progress: bool


@router.get("/", response_model=StatusResponse)
async def status():
    """Report backend and API version information.

    Returns the running application version (APP_VERSION), the current API
    major version, and the enumerable list of supported API major versions so
    a client can negotiate the API surface deliberately. Unversioned
    infrastructure — no /api/v1/ prefix (see CLAUDE.md).
    """
    return StatusResponse(
        version=APP_VERSION,
        api_version=API_VERSION,
        versions=SUPPORTED_API_VERSIONS,
    )


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
