from datetime import datetime, date
import json
from typing import Any, Dict
from sqlalchemy import delete
from sqlalchemy.ext.asyncio import AsyncSession

from ..models import Person, Chore, Settings
from ..security import hash_password
from .export_service import compute_schema_version, EXPORT_SCHEMA

DEFAULT_IMPORT_PASSWORD = "password"


def convert_iso_fields(obj: Dict[str, Any], model_type: str) -> Dict[str, Any]:
    """Convert ISO date strings back to date/datetime objects."""
    result = obj.copy()

    date_fields = {
        "chore": ["next_due"],
        "person": [],
    }

    datetime_fields = {
        "chore": ["last_changed_at", "last_completed_at"],
        "person": [],
    }

    for field in date_fields.get(model_type, []):
        if field in result and isinstance(result[field], str):
            try:
                result[field] = datetime.fromisoformat(result[field]).date()
            except (ValueError, AttributeError):
                pass

    for field in datetime_fields.get(model_type, []):
        if field in result and isinstance(result[field], str):
            try:
                result[field] = datetime.fromisoformat(result[field])
            except ValueError:
                pass

    return result


async def validate_import_data(data: Dict[str, Any]) -> tuple[bool, str]:
    """Validate import data structure and schema version."""
    if not isinstance(data, dict):
        return False, "Import data must be a JSON object"

    required_keys = {"schemaVersion", "exportDate", "config", "people", "chores"}
    if not required_keys.issubset(data.keys()):
        return False, f"Missing required keys. Expected: {required_keys}"

    current_version = compute_schema_version()
    if data.get("schemaVersion") != current_version:
        return False, f"Schema version mismatch. Expected: {current_version}, Got: {data.get('schemaVersion')}"

    if not isinstance(data.get("people"), list):
        return False, "People must be a list"
    if not isinstance(data.get("chores"), list):
        return False, "Chores must be a list"
    if not isinstance(data.get("config"), dict):
        return False, "Config must be a dictionary"

    return True, "Valid"


async def import_config(
    data: Dict[str, Any],
    db: AsyncSession,
) -> Dict[str, Any]:
    """Import configuration data (replace strategy)."""
    is_valid, message = await validate_import_data(data)
    if not is_valid:
        return {"success": False, "error": message}

    try:
        await db.execute(delete(Person))
        await db.execute(delete(Chore))
        await db.execute(delete(Settings))

        for person_data in data.get("people", []):
            converted_data = convert_iso_fields(person_data, "person")
            if "password_hash" not in converted_data or not converted_data["password_hash"]:
                converted_data["password_hash"] = hash_password(DEFAULT_IMPORT_PASSWORD)
            person = Person(
                id=converted_data.get("id"),
                name=converted_data.get("name"),
                username=converted_data.get("username"),
                password_hash=converted_data.get("password_hash"),
                is_admin=converted_data.get("is_admin", False),
                color=converted_data.get("color", "#004272"),
                goal_7d=converted_data.get("goal_7d", 20),
                goal_30d=converted_data.get("goal_30d", 80),
                preferred_theme=converted_data.get("preferred_theme"),
            )
            db.add(person)

        for chore_data in data.get("chores", []):
            converted_data = convert_iso_fields(chore_data, "chore")
            chore = Chore(**converted_data)
            db.add(chore)

        for key, value in data.get("config", {}).items():
            setting = Settings(key=key, value=value)
            db.add(setting)

        await db.commit()

        return {
            "success": True,
            "message": "Data imported successfully",
            "imported": {
                "people": len(data.get("people", [])),
                "chores": len(data.get("chores", [])),
                "settings": len(data.get("config", {})),
            },
        }
    except Exception as e:
        await db.rollback()
        return {"success": False, "error": f"Import failed: {str(e)}"}
