"""Database migrations using Alembic."""
import asyncio
import subprocess
import sys
from pathlib import Path
from sqlalchemy.ext.asyncio import AsyncSession


async def apply_migrations(db: AsyncSession):
    """Run pending Alembic migrations."""
    # Get the backend directory
    backend_dir = Path(__file__).parent.parent

    # Run Alembic upgrade in subprocess
    try:
        proc = subprocess.run(
            [sys.executable, "-m", "alembic", "upgrade", "head"],
            cwd=backend_dir,
            capture_output=True,
            text=True,
            timeout=30
        )

        if proc.returncode != 0:
            # Only log warning, don't fail startup
            # This allows for development environments where DB might not be ready
            print(f"Alembic migration warning: {proc.stderr}", file=sys.stderr)
        else:
            print("Database migrations applied successfully")
    except (subprocess.TimeoutExpired, FileNotFoundError) as e:
        print(f"Warning: Could not run migrations: {e}", file=sys.stderr)
