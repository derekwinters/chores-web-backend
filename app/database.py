from enum import Enum
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine

from .config import settings


class DatabaseStatus(Enum):
    """Database initialization status states."""
    INITIALIZING = "initializing"
    READY = "ready"
    ERROR = "error"


# Global state tracker for database initialization
_db_status = DatabaseStatus.INITIALIZING
_migrations_in_progress = False


def set_db_status(status: DatabaseStatus) -> None:
    """Update database status state."""
    global _db_status
    _db_status = status


def get_db_status() -> DatabaseStatus:
    """Get current database status."""
    return _db_status


def set_migrations_in_progress(in_progress: bool) -> None:
    """Update migration progress state."""
    global _migrations_in_progress
    _migrations_in_progress = in_progress


def get_migrations_in_progress() -> bool:
    """Check if migrations are in progress."""
    return _migrations_in_progress


engine = create_async_engine(settings.database_url, echo=False)
AsyncSessionLocal = async_sessionmaker(engine, expire_on_commit=False)


async def get_db() -> AsyncSession:
    async with AsyncSessionLocal() as session:
        yield session
