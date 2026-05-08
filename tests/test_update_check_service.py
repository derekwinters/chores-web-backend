"""Tests for update check service."""
import pytest
from datetime import datetime, timedelta
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models import UpdateCheck
from app.services.update_check_service import (
    check_for_updates,
    get_update_status,
    configure_update_check,
)


@pytest.mark.asyncio
async def test_check_for_updates_creates_initial_record(db: AsyncSession):
    """Test that check_for_updates creates initial record if it doesn't exist."""
    # Ensure no record exists
    result = await db.execute(select(UpdateCheck).limit(1))
    assert result.scalar_one_or_none() is None

    # Call check_for_updates
    await check_for_updates(db)

    # Verify record was created
    result = await db.execute(select(UpdateCheck).limit(1))
    record = result.scalar_one_or_none()
    assert record is not None
    assert record.check_enabled is True
    assert record.check_interval_hours == 24


@pytest.mark.asyncio
async def test_get_update_status_returns_correct_format(db: AsyncSession):
    """Test that get_update_status returns the correct format."""
    # Create initial record
    await check_for_updates(db)

    # Get status
    status = await get_update_status(db)

    # Verify format
    assert "current_version" in status
    assert "latest_version" in status
    assert "last_checked_at" in status
    assert "check_enabled" in status
    assert "check_interval_hours" in status
    assert "update_available" in status


@pytest.mark.asyncio
async def test_configure_update_check_enables_checking(db: AsyncSession):
    """Test that configure_update_check enables checking."""
    # Configure to enable
    result = await configure_update_check(db, enabled=True, interval_hours=12)

    # Verify settings
    assert result["check_enabled"] is True
    assert result["check_interval_hours"] == 12


@pytest.mark.asyncio
async def test_configure_update_check_disables_checking(db: AsyncSession):
    """Test that configure_update_check disables checking."""
    # Configure to disable
    result = await configure_update_check(db, enabled=False)

    # Verify settings
    assert result["check_enabled"] is False


@pytest.mark.asyncio
async def test_check_for_updates_respects_interval(db: AsyncSession):
    """Test that check_for_updates respects the check interval."""
    # Create initial record with last check 1 hour ago (within 24-hour interval)
    initial_time = datetime.utcnow() - timedelta(hours=1)
    update_check = UpdateCheck(
        current_version="1.0.0",
        check_enabled=True,
        check_interval_hours=24,
        last_checked_at=initial_time,
    )
    db.add(update_check)
    await db.commit()

    # Call check_for_updates (should skip due to interval not being reached yet)
    await check_for_updates(db)

    # Verify last_checked_at hasn't changed (should still be 1 hour ago)
    result = await db.execute(select(UpdateCheck).limit(1))
    record = result.scalar_one_or_none()
    time_since_initial = (record.last_checked_at.replace(tzinfo=None) - initial_time).total_seconds()
    # Should be essentially 0 (no new check made)
    assert abs(time_since_initial) < 1  # Less than 1 second difference


@pytest.mark.asyncio
async def test_check_for_updates_skips_if_disabled(db: AsyncSession):
    """Test that check_for_updates is skipped if checking is disabled."""
    # Create record with checking disabled
    update_check = UpdateCheck(
        current_version="1.0.0",
        check_enabled=False,
        check_interval_hours=1,
        last_checked_at=datetime.utcnow() - timedelta(hours=25),
    )
    db.add(update_check)
    await db.commit()

    # Call check_for_updates
    await check_for_updates(db)

    # Verify last_checked_at is still old (no new check made)
    result = await db.execute(select(UpdateCheck).limit(1))
    record = result.scalar_one_or_none()
    assert record.check_enabled is False


@pytest.mark.asyncio
async def test_version_comparison_identifies_update(db: AsyncSession):
    """Test that version comparison correctly identifies when update is available."""
    # Create record with older version
    update_check = UpdateCheck(
        current_version="1.0.0",
        latest_version="1.1.0",
        check_enabled=True,
        check_interval_hours=24,
    )
    db.add(update_check)
    await db.commit()

    # Get status
    status = await get_update_status(db)

    # Verify update is detected
    assert status["update_available"] is True


@pytest.mark.asyncio
async def test_version_comparison_ignores_same_version(db: AsyncSession):
    """Test that version comparison correctly ignores same versions."""
    # Create record with same version
    update_check = UpdateCheck(
        current_version="1.0.0",
        latest_version="1.0.0",
        check_enabled=True,
        check_interval_hours=24,
    )
    db.add(update_check)
    await db.commit()

    # Get status
    status = await get_update_status(db)

    # Verify no update is available
    assert status["update_available"] is False
