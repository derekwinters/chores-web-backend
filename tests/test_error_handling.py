"""Tests for structured error handling on write operations.

Verifies that:
- IntegrityError with UniqueViolationError cause → HTTP 409 + logger.warning (no stack trace)
- Generic Exception → logger.exception (full stack trace) + re-raised / HTTP 500
- Normal operations still work correctly
"""
from unittest.mock import AsyncMock, MagicMock, patch

import pytest
from fastapi import HTTPException
from sqlalchemy.exc import IntegrityError

from app.models import Chore
from app.services.chore_service import (
    complete_chore,
    initialize_chore,
    mark_due_chore,
    reassign_chore,
    skip_chore,
)


def _make_chore(**kwargs) -> Chore:
    defaults = dict(
        name="Test Chore",
        schedule_type="weekly",
        schedule_config={"days": [0]},
        assignment_type="open",
        eligible_people=[],
        points=0,
        state="due",
        rotation_index=0,
    )
    defaults.update(kwargs)
    return Chore(**defaults)


class UniqueViolationError(Exception):
    """Fake asyncpg UniqueViolationError for testing."""


class ForeignKeyViolationError(Exception):
    """Fake asyncpg ForeignKeyViolationError for testing."""


def _make_unique_violation_error() -> IntegrityError:
    """Build an IntegrityError whose .orig is a UniqueViolationError."""
    return IntegrityError("unique", {}, UniqueViolationError("duplicate key"))


def _make_generic_integrity_error() -> IntegrityError:
    """Build an IntegrityError with a non-unique orig."""
    return IntegrityError("fk", {}, ForeignKeyViolationError("fk violation"))


class TestInitializeChoreErrorHandling:
    """initialize_chore wraps db.commit in try/except."""

    @pytest.mark.asyncio
    async def test_unique_violation_raises_409(self, db):
        chore = _make_chore()
        db.add(chore)
        error = _make_unique_violation_error()
        with patch.object(db, "commit", new_callable=AsyncMock, side_effect=error):
            with patch.object(db, "rollback", new_callable=AsyncMock):
                with pytest.raises(HTTPException) as exc_info:
                    await initialize_chore(chore, db)
        assert exc_info.value.status_code == 409

    @pytest.mark.asyncio
    async def test_unique_violation_logs_warning_not_exception(self, db):
        chore = _make_chore()
        db.add(chore)
        error = _make_unique_violation_error()
        with patch("app.services.chore_service.logger") as mock_logger:
            with patch.object(db, "commit", new_callable=AsyncMock, side_effect=error):
                with patch.object(db, "rollback", new_callable=AsyncMock):
                    with pytest.raises(HTTPException):
                        await initialize_chore(chore, db)
        mock_logger.warning.assert_called_once()
        mock_logger.exception.assert_not_called()

    @pytest.mark.asyncio
    async def test_generic_exception_is_reraised(self, db):
        chore = _make_chore()
        db.add(chore)
        generic_error = RuntimeError("disk full")
        with patch.object(db, "commit", new_callable=AsyncMock, side_effect=generic_error):
            with patch.object(db, "rollback", new_callable=AsyncMock):
                with pytest.raises(RuntimeError):
                    await initialize_chore(chore, db)

    @pytest.mark.asyncio
    async def test_generic_exception_logs_full_trace(self, db):
        chore = _make_chore()
        db.add(chore)
        generic_error = RuntimeError("disk full")
        with patch("app.services.chore_service.logger") as mock_logger:
            with patch.object(db, "commit", new_callable=AsyncMock, side_effect=generic_error):
                with patch.object(db, "rollback", new_callable=AsyncMock):
                    with pytest.raises(RuntimeError):
                        await initialize_chore(chore, db)
        mock_logger.exception.assert_called_once()
        mock_logger.warning.assert_not_called()

    @pytest.mark.asyncio
    async def test_rollback_called_on_integrity_error(self, db):
        chore = _make_chore()
        db.add(chore)
        error = _make_unique_violation_error()
        with patch.object(db, "commit", new_callable=AsyncMock, side_effect=error):
            rollback_mock = AsyncMock()
            with patch.object(db, "rollback", rollback_mock):
                with pytest.raises(HTTPException):
                    await initialize_chore(chore, db)
        rollback_mock.assert_called_once()


class TestCompleteChoreErrorHandling:
    """complete_chore wraps db.commit in try/except."""

    @pytest.mark.asyncio
    async def test_unique_violation_raises_409(self, db):
        chore = _make_chore(state="due", schedule_type="interval", schedule_config={"days": 7})
        db.add(chore)
        await db.commit()
        await db.refresh(chore)

        error = _make_unique_violation_error()
        with patch.object(db, "commit", new_callable=AsyncMock, side_effect=error):
            with patch.object(db, "rollback", new_callable=AsyncMock):
                with pytest.raises(HTTPException) as exc_info:
                    await complete_chore(chore, db)
        assert exc_info.value.status_code == 409

    @pytest.mark.asyncio
    async def test_unique_violation_logs_warning_not_exception(self, db):
        chore = _make_chore(state="due", schedule_type="interval", schedule_config={"days": 7})
        db.add(chore)
        await db.commit()
        await db.refresh(chore)

        error = _make_unique_violation_error()
        with patch("app.services.chore_service.logger") as mock_logger:
            with patch.object(db, "commit", new_callable=AsyncMock, side_effect=error):
                with patch.object(db, "rollback", new_callable=AsyncMock):
                    with pytest.raises(HTTPException):
                        await complete_chore(chore, db)
        mock_logger.warning.assert_called_once()
        mock_logger.exception.assert_not_called()

    @pytest.mark.asyncio
    async def test_generic_exception_logs_full_trace(self, db):
        chore = _make_chore(state="due", schedule_type="interval", schedule_config={"days": 7})
        db.add(chore)
        await db.commit()
        await db.refresh(chore)

        generic_error = RuntimeError("connection lost")
        with patch("app.services.chore_service.logger") as mock_logger:
            with patch.object(db, "commit", new_callable=AsyncMock, side_effect=generic_error):
                with patch.object(db, "rollback", new_callable=AsyncMock):
                    with pytest.raises(RuntimeError):
                        await complete_chore(chore, db)
        mock_logger.exception.assert_called_once()
        mock_logger.warning.assert_not_called()

    @pytest.mark.asyncio
    async def test_rollback_called_on_error(self, db):
        chore = _make_chore(state="due", schedule_type="interval", schedule_config={"days": 7})
        db.add(chore)
        await db.commit()
        await db.refresh(chore)

        error = _make_unique_violation_error()
        with patch.object(db, "commit", new_callable=AsyncMock, side_effect=error):
            rollback_mock = AsyncMock()
            with patch.object(db, "rollback", rollback_mock):
                with pytest.raises(HTTPException):
                    await complete_chore(chore, db)
        rollback_mock.assert_called_once()


class TestSkipChoreErrorHandling:
    """skip_chore wraps db.commit in try/except."""

    @pytest.mark.asyncio
    async def test_unique_violation_raises_409(self, db):
        chore = _make_chore(state="due", schedule_type="interval", schedule_config={"days": 7})
        db.add(chore)
        await db.commit()
        await db.refresh(chore)

        error = _make_unique_violation_error()
        with patch.object(db, "commit", new_callable=AsyncMock, side_effect=error):
            with patch.object(db, "rollback", new_callable=AsyncMock):
                with pytest.raises(HTTPException) as exc_info:
                    await skip_chore(chore, db)
        assert exc_info.value.status_code == 409

    @pytest.mark.asyncio
    async def test_generic_exception_logs_full_trace(self, db):
        chore = _make_chore(state="due", schedule_type="interval", schedule_config={"days": 7})
        db.add(chore)
        await db.commit()
        await db.refresh(chore)

        generic_error = RuntimeError("timeout")
        with patch("app.services.chore_service.logger") as mock_logger:
            with patch.object(db, "commit", new_callable=AsyncMock, side_effect=generic_error):
                with patch.object(db, "rollback", new_callable=AsyncMock):
                    with pytest.raises(RuntimeError):
                        await skip_chore(chore, db)
        mock_logger.exception.assert_called_once()
        mock_logger.warning.assert_not_called()


class TestReassignChoreErrorHandling:
    """reassign_chore wraps db.commit in try/except."""

    @pytest.mark.asyncio
    async def test_unique_violation_raises_409(self, db):
        chore = _make_chore(state="due", schedule_type="interval", schedule_config={"days": 7})
        db.add(chore)
        await db.commit()
        await db.refresh(chore)

        error = _make_unique_violation_error()
        with patch.object(db, "commit", new_callable=AsyncMock, side_effect=error):
            with patch.object(db, "rollback", new_callable=AsyncMock):
                with pytest.raises(HTTPException) as exc_info:
                    await reassign_chore(chore, db, assignee="Alice")
        assert exc_info.value.status_code == 409

    @pytest.mark.asyncio
    async def test_generic_exception_logs_full_trace(self, db):
        chore = _make_chore(state="due", schedule_type="interval", schedule_config={"days": 7})
        db.add(chore)
        await db.commit()
        await db.refresh(chore)

        generic_error = RuntimeError("timeout")
        with patch("app.services.chore_service.logger") as mock_logger:
            with patch.object(db, "commit", new_callable=AsyncMock, side_effect=generic_error):
                with patch.object(db, "rollback", new_callable=AsyncMock):
                    with pytest.raises(RuntimeError):
                        await reassign_chore(chore, db, assignee="Alice")
        mock_logger.exception.assert_called_once()
        mock_logger.warning.assert_not_called()


class TestMarkDueChoreErrorHandling:
    """mark_due_chore wraps db.commit in try/except."""

    @pytest.mark.asyncio
    async def test_unique_violation_raises_409(self, db):
        chore = _make_chore(state="complete", schedule_type="interval", schedule_config={"days": 7})
        db.add(chore)
        await db.commit()
        await db.refresh(chore)

        error = _make_unique_violation_error()
        with patch.object(db, "commit", new_callable=AsyncMock, side_effect=error):
            with patch.object(db, "rollback", new_callable=AsyncMock):
                with pytest.raises(HTTPException) as exc_info:
                    await mark_due_chore(chore, db)
        assert exc_info.value.status_code == 409

    @pytest.mark.asyncio
    async def test_generic_exception_logs_full_trace(self, db):
        chore = _make_chore(state="complete", schedule_type="interval", schedule_config={"days": 7})
        db.add(chore)
        await db.commit()
        await db.refresh(chore)

        generic_error = RuntimeError("timeout")
        with patch("app.services.chore_service.logger") as mock_logger:
            with patch.object(db, "commit", new_callable=AsyncMock, side_effect=generic_error):
                with patch.object(db, "rollback", new_callable=AsyncMock):
                    with pytest.raises(RuntimeError):
                        await mark_due_chore(chore, db)
        mock_logger.exception.assert_called_once()
        mock_logger.warning.assert_not_called()


class TestRouterCreateChoreErrorHandling:
    """HTTP router create_chore returns 409 for duplicate chore names."""

    @pytest.mark.asyncio
    async def test_duplicate_name_returns_409(self, authenticated_client):
        """Creating a chore with a duplicate name returns HTTP 409."""
        create_body = {
            "name": "Error Test Chore",
            "schedule_type": "interval",
            "schedule_config": {"days": 7},
            "assignment_type": "open",
            "eligible_people": [],
            "points": 0,
        }
        r = await authenticated_client.post("/chores", json=create_body)
        assert r.status_code == 201

        # Second identical request should 409
        r2 = await authenticated_client.post("/chores", json=create_body)
        assert r2.status_code == 409

    @pytest.mark.asyncio
    async def test_chores_router_logs_warning_on_integrity_error(self, db):
        """IntegrityError on commit in create_chore logs a warning, not an exception."""
        from app.routers.chores import create_chore
        from app.schemas import ChoreCreate

        body = ChoreCreate(
            name="Integrity Error Chore",
            schedule_type="interval",
            schedule_config={"days": 7},
            assignment_type="open",
            eligible_people=[],
            points=0,
        )
        error = _make_unique_violation_error()
        with patch("app.routers.chores.initialize_chore", new_callable=AsyncMock):
            with patch("app.routers.chores.log_chore_change", new_callable=AsyncMock):
                with patch("app.routers.chores.logger") as mock_logger:
                    with patch.object(db, "commit", new_callable=AsyncMock, side_effect=error):
                        with patch.object(db, "rollback", new_callable=AsyncMock):
                            with patch.object(db, "flush", new_callable=AsyncMock):
                                with pytest.raises(HTTPException) as exc_info:
                                    await create_chore(body=body, current_user="testuser", db=db)
        assert exc_info.value.status_code == 409
        mock_logger.warning.assert_called_once()
        mock_logger.exception.assert_not_called()
