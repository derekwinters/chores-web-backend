"""Unit tests for database migration startup logic in app/migrations.py."""
import subprocess
from unittest.mock import AsyncMock, MagicMock, call, patch

import pytest

from app.database import DatabaseStatus
from app.migrations import apply_migrations, _INITIAL_REVISION


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _make_proc(returncode: int = 0, stdout: str = "", stderr: str = "") -> MagicMock:
    """Return a mock CompletedProcess."""
    proc = MagicMock()
    proc.returncode = returncode
    proc.stdout = stdout
    proc.stderr = stderr
    return proc


# ---------------------------------------------------------------------------
# Test: normal success path
# ---------------------------------------------------------------------------

@pytest.mark.asyncio
async def test_apply_migrations_success_path():
    """Normal upgrade with no errors sets status to READY."""
    db = AsyncMock()
    success_proc = _make_proc(returncode=0, stdout="", stderr="")

    with patch("app.migrations.subprocess.run", return_value=success_proc) as mock_run, \
         patch("app.migrations.set_db_status") as mock_set_status, \
         patch("app.migrations.set_migrations_in_progress") as mock_in_progress:

        await apply_migrations(db)

        mock_set_status.assert_called_once_with(DatabaseStatus.READY)
        # upgrade called exactly once
        assert mock_run.call_count == 1
        assert "upgrade" in mock_run.call_args[0][0]


# ---------------------------------------------------------------------------
# Test: error path (non-duplicate failure)
# ---------------------------------------------------------------------------

@pytest.mark.asyncio
async def test_apply_migrations_error_path():
    """A non-duplicate error sets status to ERROR."""
    db = AsyncMock()
    error_proc = _make_proc(returncode=1, stdout="", stderr="FATAL: connection refused")

    with patch("app.migrations.subprocess.run", return_value=error_proc), \
         patch("app.migrations.set_db_status") as mock_set_status, \
         patch("app.migrations.set_migrations_in_progress"):

        await apply_migrations(db)

        mock_set_status.assert_called_once_with(DatabaseStatus.ERROR)


# ---------------------------------------------------------------------------
# Test: "already exists" in stderr does NOT trigger stamping
# ---------------------------------------------------------------------------

@pytest.mark.asyncio
async def test_apply_migrations_does_not_stamp_on_arbitrary_already_exists():
    """'already exists' without 'DuplicateTable' is treated as a real error, not a stamp trigger."""
    db = AsyncMock()
    # Some other error message that happens to include "already exists"
    error_proc = _make_proc(returncode=1, stdout="", stderr="constraint already exists")

    with patch("app.migrations.subprocess.run", return_value=error_proc), \
         patch("app.migrations.set_db_status") as mock_set_status, \
         patch("app.migrations.set_migrations_in_progress"):

        await apply_migrations(db)

        # Should be ERROR, not READY — stamping must NOT be triggered
        mock_set_status.assert_called_once_with(DatabaseStatus.ERROR)


# ---------------------------------------------------------------------------
# Test: DuplicateTable when already at head → no stamp, READY
# ---------------------------------------------------------------------------

@pytest.mark.asyncio
async def test_apply_migrations_already_at_head_skips_stamp():
    """When DuplicateTable appears but current revision is already head, skip stamping."""
    db = AsyncMock()
    dup_proc = _make_proc(returncode=1, stderr="DuplicateTable: relation 'chores' already exists")
    current_proc = _make_proc(returncode=0, stdout="b2c3d4e5f6a1 (head)")

    with patch("app.migrations.subprocess.run", side_effect=[dup_proc, current_proc]) as mock_run, \
         patch("app.migrations.set_db_status") as mock_set_status, \
         patch("app.migrations.set_migrations_in_progress"):

        await apply_migrations(db)

        mock_set_status.assert_called_once_with(DatabaseStatus.READY)
        # upgrade + current — no stamp or second upgrade
        assert mock_run.call_count == 2


# ---------------------------------------------------------------------------
# Test: DuplicateTable stamps initial revision then re-runs upgrade
# ---------------------------------------------------------------------------

@pytest.mark.asyncio
async def test_apply_migrations_stamps_initial_then_reruns_upgrade():
    """DuplicateTable with pending migrations stamps initial revision and re-runs upgrade."""
    db = AsyncMock()
    dup_proc    = _make_proc(returncode=1, stderr="DuplicateTable: relation 'chores' already exists")
    current_proc = _make_proc(returncode=0, stdout="6809073594f7")   # at initial, not head
    stamp_proc  = _make_proc(returncode=0)
    upgrade2_proc = _make_proc(returncode=0)

    side_effects = [dup_proc, current_proc, stamp_proc, upgrade2_proc]

    with patch("app.migrations.subprocess.run", side_effect=side_effects) as mock_run, \
         patch("app.migrations.set_db_status") as mock_set_status, \
         patch("app.migrations.set_migrations_in_progress"):

        await apply_migrations(db)

        mock_set_status.assert_called_once_with(DatabaseStatus.READY)
        calls = mock_run.call_args_list

        # First call: upgrade head
        assert "upgrade" in calls[0][0][0]
        # Second call: alembic current
        assert "current" in calls[1][0][0]
        # Third call: stamp _INITIAL_REVISION
        assert "stamp" in calls[2][0][0]
        assert _INITIAL_REVISION in calls[2][0][0]
        # Fourth call: upgrade head again
        assert "upgrade" in calls[3][0][0]


# ---------------------------------------------------------------------------
# Test: pending migrations still run after stamp (resync migration executes)
# ---------------------------------------------------------------------------

@pytest.mark.asyncio
async def test_apply_migrations_pending_migrations_run_after_stamp():
    """After stamping the initial revision, the re-run upgrade processes pending migrations."""
    db = AsyncMock()
    dup_proc     = _make_proc(returncode=1, stderr="DuplicateTable: relation 'people' already exists")
    current_proc = _make_proc(returncode=0, stdout="")   # empty — not at head
    stamp_proc   = _make_proc(returncode=0)
    # Simulate the resync migration running during the second upgrade
    upgrade2_proc = _make_proc(
        returncode=0,
        stdout="Running upgrade 6809073594f7 -> b2c3d4e5f6a1, Resync sequences to table data"
    )

    with patch("app.migrations.subprocess.run",
               side_effect=[dup_proc, current_proc, stamp_proc, upgrade2_proc]) as mock_run, \
         patch("app.migrations.set_db_status") as mock_set_status, \
         patch("app.migrations.set_migrations_in_progress"):

        await apply_migrations(db)

        mock_set_status.assert_called_once_with(DatabaseStatus.READY)
        # Confirm four subprocess calls were made
        assert mock_run.call_count == 4
        # The second upgrade output mentions the resync migration
        last_call_result = mock_run.call_args_list[3]
        assert "upgrade" in last_call_result[0][0]
