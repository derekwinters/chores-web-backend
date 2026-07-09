"""Built-in theme palettes are vendored from @chores/design-tokens (values-only).

See derekwinters/chores-web-backend#21 / master rollout derekwinters/chores-web-docs#11:
the token repo is the source of truth for the six built-in palettes; this backend
loads them from the vendored ``app/data/themes.json`` instead of hardcoding hex
values in ``app/routers/theme.py``. The API schema is unchanged.
"""
import json
import re
from pathlib import Path

BACKEND_ROOT = Path(__file__).resolve().parent.parent
VENDORED_FILE = BACKEND_ROOT / "app" / "data" / "themes.json"
THEME_MODULE = BACKEND_ROOT / "app" / "routers" / "theme.py"
UPDATE_SCRIPT = BACKEND_ROOT / "scripts" / "update_themes.py"

SLOTS = [
    "bg",
    "surface",
    "surface2",
    "accent",
    "primary",
    "secondary",
    "success",
    "warning",
    "error",
]
BUILTIN_THEMES = ["dark", "light", "charcoal", "paper", "pink", "frog"]
HEX_RE = re.compile(r"^#[0-9a-fA-F]{6}$")


def load_vendored():
    assert VENDORED_FILE.exists(), "app/data/themes.json must be vendored"
    return json.loads(VENDORED_FILE.read_text())


def vendored_themes():
    return {k: v for k, v in load_vendored().items() if not k.startswith("_")}


def test_vendored_file_pins_its_token_source():
    meta = load_vendored().get("_source", "")
    assert "@chores/design-tokens@" in meta


def test_vendored_file_has_exactly_the_builtin_themes():
    assert sorted(vendored_themes()) == sorted(BUILTIN_THEMES)


def test_every_theme_has_exactly_the_nine_slots_with_valid_hex():
    for name, slots in vendored_themes().items():
        assert sorted(slots) == sorted(SLOTS), f"{name} slots mismatch"
        for slot, value in slots.items():
            assert HEX_RE.match(value), f"{name}.{slot} = {value!r} is not #rrggbb"


def test_default_themes_are_loaded_from_the_vendored_file():
    from app.routers.theme import DEFAULT_THEMES

    vendored = vendored_themes()
    assert sorted(DEFAULT_THEMES) == sorted(vendored)
    for theme_id, slots in vendored.items():
        theme = DEFAULT_THEMES[theme_id]
        assert theme.id == theme_id
        assert theme.name == theme_id.capitalize()
        for slot, value in slots.items():
            assert getattr(theme.colors, slot) == value, f"{theme_id}.{slot}"


def test_theme_module_contains_no_hardcoded_palette_hex():
    source = THEME_MODULE.read_text()
    for name, slots in vendored_themes().items():
        for slot, value in slots.items():
            assert value not in source, (
                f"{value} ({name}.{slot}) is hardcoded in theme.py — "
                "palettes must come from app/data/themes.json"
            )


def test_update_script_exists_and_names_the_package():
    assert UPDATE_SCRIPT.exists(), "scripts/update_themes.py must exist"
    text = UPDATE_SCRIPT.read_text()
    assert "@chores/design-tokens" in text
