"""Database migrations for schema updates."""
from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession


async def apply_migrations(db: AsyncSession):
    """Apply pending migrations. Safe to run multiple times."""
    async with db.begin():
        # Check if points_redeemed column exists
        result = await db.execute(text("""
            SELECT EXISTS (
                SELECT 1 FROM information_schema.columns
                WHERE table_name = 'people' AND column_name = 'points_redeemed'
            )
        """))
        column_exists = result.scalar()

        if not column_exists:
            await db.execute(text(
                'ALTER TABLE people ADD COLUMN points_redeemed INTEGER NOT NULL DEFAULT 0'
            ))

        # Check if redemption_log table exists
        result = await db.execute(text("""
            SELECT EXISTS (
                SELECT 1 FROM information_schema.tables
                WHERE table_name = 'redemption_log'
            )
        """))
        table_exists = result.scalar()

        if not table_exists:
            await db.execute(text("""
                CREATE TABLE redemption_log (
                    id SERIAL PRIMARY KEY,
                    person_id INTEGER NOT NULL,
                    amount INTEGER NOT NULL,
                    redeemed_by TEXT NOT NULL,
                    timestamp TIMESTAMP WITH TIME ZONE NOT NULL
                )
            """))
