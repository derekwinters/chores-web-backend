import pytest
from datetime import date, datetime
from sqlalchemy.ext.asyncio import AsyncSession

from app.services.import_service import validate_import_data, import_config, convert_iso_fields
from app.models import Person, Chore, Settings


@pytest.mark.asyncio
class TestImportValidation:
    async def test_validate_import_data_missing_keys(self):
        data = {"schemaVersion": "abc123"}
        is_valid, message = await validate_import_data(data)
        assert not is_valid
        assert "Missing required keys" in message

    async def test_validate_import_data_invalid_schema_version(self):
        data = {
            "schemaVersion": "invalid",
            "exportDate": "2026-04-25T00:00:00",
            "config": {},
            "people": [],
            "chores": [],
        }
        is_valid, message = await validate_import_data(data)
        assert not is_valid
        assert "Schema version mismatch" in message

    async def test_validate_import_data_people_not_list(self):
        from app.services.export_service import compute_schema_version

        data = {
            "schemaVersion": compute_schema_version(),
            "exportDate": "2026-04-25T00:00:00",
            "config": {},
            "people": {},
            "chores": [],
        }
        is_valid, message = await validate_import_data(data)
        assert not is_valid
        assert "People must be a list" in message

    async def test_validate_import_data_valid(self):
        from app.services.export_service import compute_schema_version

        data = {
            "schemaVersion": compute_schema_version(),
            "exportDate": "2026-04-25T00:00:00",
            "config": {},
            "people": [],
            "chores": [],
        }
        is_valid, message = await validate_import_data(data)
        assert is_valid
        assert message == "Valid"


class TestConvertIsoFields:
    def test_convert_chore_date_fields(self):
        data = {"id": 1, "name": "Test", "next_due": "2026-05-24"}
        result = convert_iso_fields(data, "chore")
        assert isinstance(result["next_due"], date)
        assert result["next_due"] == date(2026, 5, 24)

    def test_convert_chore_datetime_fields(self):
        data = {"id": 1, "last_changed_at": "2026-04-25T10:30:00"}
        result = convert_iso_fields(data, "chore")
        assert isinstance(result["last_changed_at"], datetime)

    def test_convert_preserves_other_fields(self):
        data = {"id": 1, "name": "Test", "points": 5, "next_due": "2026-05-24"}
        result = convert_iso_fields(data, "chore")
        assert result["id"] == 1
        assert result["name"] == "Test"
        assert result["points"] == 5

    def test_convert_person_no_date_fields(self):
        data = {"id": 1, "name": "Test", "username": "test"}
        result = convert_iso_fields(data, "person")
        assert result == data

    def test_convert_handles_invalid_iso_string(self):
        data = {"id": 1, "next_due": "invalid-date"}
        result = convert_iso_fields(data, "chore")
        assert result["next_due"] == "invalid-date"


@pytest.mark.asyncio
class TestImportConfig:
    async def test_import_creates_people(self, db: AsyncSession):
        from app.services.export_service import compute_schema_version

        data = {
            "schemaVersion": compute_schema_version(),
            "exportDate": "2026-04-25T00:00:00",
            "config": {},
            "people": [
                {
                    "id": 1,
                    "name": "Test User",
                    "username": "testuser",
                    "is_admin": False,
                    "color": "#000000",
                    "goal_7d": 20,
                    "goal_30d": 80,
                }
            ],
            "chores": [],
        }
        result = await import_config(data, db)
        assert result["success"]
        assert result["imported"]["people"] == 1

        person = await db.get(Person, 1)
        assert person is not None
        assert person.name == "Test User"
        assert person.password_hash == "password"

    async def test_import_creates_chores(self, db: AsyncSession):
        from app.services.export_service import compute_schema_version

        data = {
            "schemaVersion": compute_schema_version(),
            "exportDate": "2026-04-25T00:00:00",
            "config": {},
            "people": [],
            "chores": [
                {
                    "id": 1,
                    "name": "Test Chore",
                    "schedule_type": "interval",
                    "schedule_config": {"days": 7},
                    "assignment_type": "open",
                    "eligible_people": [],
                    "points": 5,
                    "state": "complete",
                    "disabled": False,
                    "next_due": "2026-05-24",
                }
            ],
        }
        result = await import_config(data, db)
        assert result["success"]
        assert result["imported"]["chores"] == 1

        chore = await db.get(Chore, 1)
        assert chore is not None
        assert chore.name == "Test Chore"

    async def test_import_creates_settings(self, db: AsyncSession):
        from app.services.export_service import compute_schema_version

        data = {
            "schemaVersion": compute_schema_version(),
            "exportDate": "2026-04-25T00:00:00",
            "config": {"key1": "value1", "key2": "value2"},
            "people": [],
            "chores": [],
        }
        result = await import_config(data, db)
        assert result["success"]
        assert result["imported"]["settings"] == 2

    async def test_import_replaces_existing_data(self, db: AsyncSession):
        from app.services.export_service import compute_schema_version

        person = Person(
            name="Old User", username="olduser", password_hash="hash", is_admin=False
        )
        db.add(person)
        await db.commit()

        data = {
            "schemaVersion": compute_schema_version(),
            "exportDate": "2026-04-25T00:00:00",
            "config": {},
            "people": [
                {
                    "id": 2,
                    "name": "New User",
                    "username": "newuser",
                    "is_admin": False,
                    "color": "#000000",
                    "goal_7d": 20,
                    "goal_30d": 80,
                }
            ],
            "chores": [],
        }
        result = await import_config(data, db)
        assert result["success"]

        old_person = await db.get(Person, 1)
        assert old_person is None
        new_person = await db.get(Person, 2)
        assert new_person is not None

    async def test_import_handles_invalid_schema(self, db: AsyncSession):
        data = {"schemaVersion": "invalid"}
        result = await import_config(data, db)
        assert not result["success"]
        assert "error" in result
