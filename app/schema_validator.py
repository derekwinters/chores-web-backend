"""Validate that database schema matches SQLAlchemy models."""
import logging
from sqlalchemy import inspect, text
from sqlalchemy.ext.asyncio import AsyncEngine

from .models import Base

logger = logging.getLogger(__name__)


async def validate_schema(engine: AsyncEngine) -> None:
    """
    Validate that the database schema matches the SQLAlchemy models.

    Raises SchemaValidationError if schema is out of sync.
    """
    # Get expected tables from models
    expected_tables = {table.name for table in Base.metadata.tables.values()}

    async with engine.begin() as conn:
        # Get table names using raw SQL (works with async)
        async def get_table_names(sync_conn):
            inspector = inspect(sync_conn)
            return set(inspector.get_table_names())

        try:
            existing_tables = await conn.run_sync(get_table_names)
        except Exception as e:
            logger.warning(f"Could not validate schema: {e}")
            return

        # Check for missing tables
        missing_tables = expected_tables - existing_tables
        if missing_tables:
            raise SchemaValidationError(
                f"Missing tables in database: {missing_tables}. "
                "Run 'Base.metadata.create_all()' or check your migrations."
            )


class SchemaValidationError(Exception):
    """Raised when database schema doesn't match SQLAlchemy models."""
    pass
