import logging
import sys
from contextlib import asynccontextmanager

from fastapi import Depends, FastAPI, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse
from prometheus_fastapi_instrumentator import Instrumentator
from sqlalchemy.ext.asyncio import AsyncSession

from .database import engine, get_db
from .models import Base
from .routers import auth, chores, people, points, log, config, theme, export, data_import, status, admin_db, metrics, notifications
from .schemas import VersionOut
from .services.scheduler import start_scheduler, stop_scheduler
from .services.chore_service import transition_overdue_chores, normalize_points_log_persons
from .services.update_check_service import get_public_version_info
from .database import AsyncSessionLocal
from .migrations import apply_migrations


logging.basicConfig(
    stream=sys.stdout,
    format='%(message)s',
    level=logging.INFO,
)
logger = logging.getLogger('app.services.logging')


@asynccontextmanager
async def lifespan(app: FastAPI):
    # Apply database migrations
    async with AsyncSessionLocal() as db:
        await apply_migrations(db)
        await normalize_points_log_persons(db)
        await transition_overdue_chores(db)

    async with AsyncSessionLocal() as db:
        from .routers.config import _get_due_time_hour, _get_timezone
        due_hour = await _get_due_time_hour(db)
        tz = await _get_timezone(db)

    start_scheduler(due_hour=due_hour, timezone=tz)
    yield
    stop_scheduler()


app = FastAPI(
    title="Chores API",
    description="REST API for managing household chores, assignments, and tracking",
    version="0.0.1",
    openapi_url="/openapi.json",
    docs_url="/docs",
    redoc_url="/redoc",
    lifespan=lifespan,
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_methods=["*"],
    allow_headers=["*"],
)
# HTTP request metrics via prometheus-fastapi-instrumentator (actively
# maintained, FastAPI-native). It registers its metrics on prometheus_client's
# default REGISTRY, so the existing GET /metrics endpoint (app/routers/metrics.py),
# which calls generate_latest() on that registry, serves them alongside the
# hand-rolled application gauges. We instrument only (no .expose()) — the
# metrics router owns the /metrics endpoint.
Instrumentator().instrument(app)


@app.exception_handler(Exception)
async def global_exception_handler(request: Request, exc: Exception):
    """Global exception handler for unhandled errors. Returns user-friendly message."""
    logger.error(f"Unhandled exception: {exc}", exc_info=True)
    return JSONResponse(
        status_code=500,
        content={"detail": "Something went wrong. Please try again."},
    )


V1_PREFIX = "/v1"

app.include_router(auth.router, prefix=V1_PREFIX)
app.include_router(chores.router, prefix=V1_PREFIX)
app.include_router(people.router, prefix=V1_PREFIX)
app.include_router(points.router, prefix=V1_PREFIX)
app.include_router(log.router, prefix=V1_PREFIX)
app.include_router(config.router, prefix=V1_PREFIX)
app.include_router(theme.router, prefix=V1_PREFIX)
app.include_router(export.router, prefix=V1_PREFIX)
app.include_router(data_import.router, prefix=V1_PREFIX)
app.include_router(admin_db.router, prefix=V1_PREFIX)
app.include_router(notifications.router, prefix=V1_PREFIX)
# Status and metrics are unversioned — infrastructure, not API resources
app.include_router(status.router)
# Metrics router registered without auth dependency — public endpoint
app.include_router(metrics.router)


@app.get("/health")
async def health():
    return {"status": "ok"}


@app.get("/version", response_model=VersionOut)
async def get_version(db: AsyncSession = Depends(get_db)):
    """Public, unauthenticated backend self-version check.

    Same trust tier as /health — no Authorization required. Used by
    chores-web-frontend / chores-web-android to show "Backend version" on
    their About screens; a real "not yet checked" state (null
    latest_version/checked_at) is a normal response here, distinct from this
    route not existing at all (old backends predating this endpoint).
    """
    info = await get_public_version_info(db)
    return VersionOut(**info)
