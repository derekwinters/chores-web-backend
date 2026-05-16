import logging
import sys
from contextlib import asynccontextmanager

from fastapi import FastAPI, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse

from .database import engine
from .models import Base
from .routers import auth, chores, people, points, log, config, theme, export, data_import, status, admin_db
from .services.scheduler import start_scheduler, stop_scheduler
from .services.chore_service import transition_overdue_chores
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
        await transition_overdue_chores(db)

    start_scheduler()
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


@app.exception_handler(Exception)
async def global_exception_handler(request: Request, exc: Exception):
    """Global exception handler for unhandled errors. Returns user-friendly message."""
    logger.error(f"Unhandled exception: {exc}", exc_info=True)
    return JSONResponse(
        status_code=500,
        content={"detail": "Something went wrong. Please try again."},
    )


app.include_router(auth.router)
app.include_router(chores.router)
app.include_router(people.router)
app.include_router(points.router)
app.include_router(log.router)
app.include_router(config.router)
app.include_router(theme.router)
app.include_router(export.router)
app.include_router(data_import.router)
app.include_router(status.router)
app.include_router(admin_db.router)


@app.get("/health")
async def health():
    return {"status": "ok"}
