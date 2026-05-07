"""Database migrations using Alembic."""
import asyncio
import subprocess
import sys
from pathlib import Path
from sqlalchemy.ext.asyncio import AsyncSession

from .database import set_db_status, set_migrations_in_progress, DatabaseStatus


async def apply_migrations(db: AsyncSession):
    """Run pending Alembic migrations."""
    backend_dir = Path(__file__).parent.parent
    set_migrations_in_progress(True)

    try:
        proc = subprocess.run(
            [sys.executable, "-m", "alembic", "upgrade", "head"],
            cwd=backend_dir,
            capture_output=True,
            text=True,
            timeout=30
        )

        # Check for "DuplicateTable" error (existing schema) - not a failure
        if "DuplicateTable" in proc.stderr or "already exists" in proc.stderr:
            # Schema already exists from previous run, stamp as applied
            print("Database schema already exists, marking migrations as applied")
            try:
                stamp_proc = subprocess.run(
                    [sys.executable, "-m", "alembic", "stamp", "head"],
                    cwd=backend_dir,
                    capture_output=True,
                    text=True,
                    timeout=10
                )
                if stamp_proc.returncode == 0:
                    set_db_status(DatabaseStatus.READY)
                    print("Database migrations stamped successfully")
                else:
                    print(f"Warning stamping migrations: {stamp_proc.stderr}", file=sys.stderr)
                    set_db_status(DatabaseStatus.READY)
            except Exception as e:
                print(f"Warning: Could not stamp migrations: {e}", file=sys.stderr)
                set_db_status(DatabaseStatus.READY)
        elif proc.returncode != 0:
            set_db_status(DatabaseStatus.ERROR)
            print(f"Alembic migration warning: {proc.stderr}", file=sys.stderr)
        else:
            set_db_status(DatabaseStatus.READY)
            print("Database migrations applied successfully")
    except (subprocess.TimeoutExpired, FileNotFoundError) as e:
        set_db_status(DatabaseStatus.ERROR)
        print(f"Warning: Could not run migrations: {e}", file=sys.stderr)
    finally:
        set_migrations_in_progress(False)
