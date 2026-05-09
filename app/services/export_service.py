from datetime import datetime, timezone
import hashlib
import json
from typing import Any

EXPORT_SCHEMA = {
    "person": ["id", "name", "username", "is_admin", "color", "goal_7d", "goal_30d", "preferred_theme"],
    "chore": ["id", "name", "schedule_type", "schedule_config", "assignment_type", "eligible_people", "assignee", "points", "state", "disabled", "next_due", "current_assignee", "rotation_index"],
    "settings": ["key", "value"],
}


def compute_schema_version() -> str:
    schema_str = json.dumps(EXPORT_SCHEMA, sort_keys=True)
    hash_obj = hashlib.sha256(schema_str.encode())
    return hash_obj.hexdigest()[:8]


def extract_fields(obj: Any, model_type: str) -> dict:
    fields = EXPORT_SCHEMA.get(model_type, [])
    result = {}
    for field in fields:
        if hasattr(obj, field):
            value = getattr(obj, field)
            if isinstance(value, datetime):
                value = value.isoformat()
            result[field] = value
    return result


BOOL_CONFIG_KEYS = {"auth_enabled", "update_check_enabled"}
INT_CONFIG_KEYS = {"due_soon_days", "update_check_interval"}


def coerce_config_value(key: str, value: str) -> Any:
    """Coerce a string setting value to its proper Python type for JSON export.

    Handles both old Python-stringified booleans ("True"/"False") and
    canonical lowercase forms ("true"/"false") so exports always contain
    real JSON booleans and integers rather than quoted strings.
    """
    if key in BOOL_CONFIG_KEYS:
        return value.lower() == "true"
    if key in INT_CONFIG_KEYS:
        try:
            return int(value)
        except (ValueError, TypeError):
            return value
    return value


async def generate_export(people: list, chores: list, settings: list) -> dict:
    schema_version = compute_schema_version()

    config_dict = {}
    for setting in settings:
        config_dict[setting.key] = coerce_config_value(setting.key, setting.value)

    return {
        "schemaVersion": schema_version,
        "exportDate": datetime.now(timezone.utc).isoformat(),
        "config": config_dict,
        "people": [extract_fields(p, "person") for p in people],
        "chores": [extract_fields(c, "chore") for c in chores],
    }
