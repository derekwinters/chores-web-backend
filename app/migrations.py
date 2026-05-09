"""Database migrations using Alembic."""
import subprocess
import sys
from pathlib import Path
from sqlalchemy.ext.asyncio import AsyncSession

from .database import set_db_status, set_migrations_in_progress, DatabaseStatus

# Revision that establishes the initial schema — used as a safe stamp target
# when the database already has tables but no Alembic version row yet.
_INITIAL_REVISION = '6809073594f7'


def _get_current_revision(backend_dir: Path) -> str | None:
    """Return the current Alembic revision, or None if unavailable."""
    try:
        proc = subprocess.run(
            [sys.executable, "-m", "alembic", "current"],
            cwd=backend_dir,
            capture_output=True,
            text=True,
            timeout=10
        )
        if proc.returncode == 0:
            return proc.stdout.strip()
    except Exception:
        pass
    return None


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

        # Check for "DuplicateTable" error indicating a pre-existing schema
        # that was created before Alembic tracking began.
        if "DuplicateTable" in proc.stderr:
            current = _get_current_revision(backend_dir)

            if current and "(head)" in current:
                # Already fully up-to-date — nothing to do.
                set_db_status(DatabaseStatus.READY)
                print("Database already at head revision, no migrations needed")
                return

            # Stamp only the initial revision so that all later migrations
            # (including sequence resync) still execute on the next upgrade.
            print(
                "Pre-existing schema detected (DuplicateTable). "
                f"Stamping initial revision {_INITIAL_REVISION} and re-running upgrade."
            )
            try:
                stamp_proc = subprocess.run(
                    [sys.executable, "-m", "alembic", "stamp", _INITIAL_REVISION],
                    cwd=backend_dir,
                    capture_output=True,
                    text=True,
                    timeout=10
                )
                if stamp_proc.returncode != 0:
                    print(
                        f"Warning stamping initial revision: {stamp_proc.stderr}",
                        file=sys.stderr
                    )

                # Re-run upgrade so pending migrations execute.
                upgrade_proc = subprocess.run(
                    [sys.executable, "-m", "alembic", "upgrade", "head"],
                    cwd=backend_dir,
                    capture_output=True,
                    text=True,
                    timeout=30
                )
                if upgrade_proc.returncode == 0:
                    set_db_status(DatabaseStatus.READY)
                    print("Database migrations applied successfully after stamp")
                else:
                    print(
                        f"Alembic migration warning after stamp: {upgrade_proc.stderr}",
                        file=sys.stderr
                    )
                    set_db_status(DatabaseStatus.ERROR)
            except Exception as e:
                print(f"Warning: Could not stamp/upgrade migrations: {e}", file=sys.stderr)
                set_db_status(DatabaseStatus.ERROR)
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
