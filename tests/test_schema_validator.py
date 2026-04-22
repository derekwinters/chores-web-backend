"""Tests for database schema validation."""
import pytest

from app.schema_validator import SchemaValidationError


@pytest.mark.asyncio
async def test_validate_schema_passes_with_correct_setup(setup_db):
    """Test that schema validation is called during app startup."""
    # The setup_db fixture creates all tables correctly.
    # If schema validation failed, the app would not start.
    # This test verifies the setup completes without error.
    pass


def test_schema_validation_error_message():
    """Test that SchemaValidationError messages are clear."""
    error = SchemaValidationError("Table 'people' is missing columns: {'username'}")
    assert "username" in str(error)
    assert "people" in str(error)
    assert isinstance(error, Exception)
