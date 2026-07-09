import json
from pathlib import Path

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from ..database import get_db
from ..models import Person, Settings
from ..schemas import ThemeOut, ThemeCurrentOut, ThemeDefaultInfo, ThemeSave, ThemeColors, ThemeUpdate
from ..dependencies import get_current_user, require_admin

router = APIRouter(prefix="/theme", tags=["theme"])

# Built-in palettes are design data owned by chores-web-design-tokens and
# vendored at app/data/themes.json (refresh: scripts/update_themes.py).
# Keys starting with "_" are metadata (e.g. the pinned token version).
_THEMES_FILE = Path(__file__).resolve().parent.parent / "data" / "themes.json"


def _load_default_themes() -> dict[str, ThemeOut]:
    raw = json.loads(_THEMES_FILE.read_text())
    return {
        theme_id: ThemeOut(
            id=theme_id,
            name=theme_id.capitalize(),
            colors=ThemeColors(**slots),
        )
        for theme_id, slots in raw.items()
        if not theme_id.startswith("_")
    }


DEFAULT_THEMES = _load_default_themes()

# Custom themes (in-memory, would be database in production)
_custom_themes: dict = {}


async def _get_default_theme(db: AsyncSession) -> str:
    """Get default theme ID from database. Returns 'paper' if not set."""
    result = await db.execute(select(Settings).where(Settings.key == "default_theme"))
    settings_row = result.scalar_one_or_none()
    return settings_row.value if settings_row else "paper"


async def _set_default_theme(db: AsyncSession, theme_id: str) -> None:
    """Persist default theme ID to database."""
    result = await db.execute(select(Settings).where(Settings.key == "default_theme"))
    settings_row = result.scalar_one_or_none()
    if settings_row:
        settings_row.value = theme_id
    else:
        settings_row = Settings(key="default_theme", value=theme_id)
        db.add(settings_row)
    await db.commit()


@router.get("/list", response_model=list[ThemeOut])
async def list_themes(current_user: str = Depends(get_current_user), db: AsyncSession = Depends(get_db)):
    themes = list(DEFAULT_THEMES.values()) + list(_custom_themes.values())
    return themes


@router.get("/current", response_model=ThemeCurrentOut)
async def get_current_theme(current_user: str = Depends(get_current_user), db: AsyncSession = Depends(get_db)):
    result = await db.execute(select(Person).where(Person.username == current_user))
    person = result.scalars().first()

    has_personal = bool(person and person.preferred_theme)
    default_theme_id = await _get_default_theme(db)
    theme_id = person.preferred_theme if has_personal else default_theme_id

    if theme_id in DEFAULT_THEMES:
        theme = DEFAULT_THEMES[theme_id]
    else:
        theme = _custom_themes.get(theme_id, DEFAULT_THEMES["paper"])

    return ThemeCurrentOut(id=theme.id, name=theme.name, colors=theme.colors, is_personal=has_personal)


@router.get("/default", response_model=ThemeOut)
async def get_default_theme(current_user: str = Depends(require_admin), db: AsyncSession = Depends(get_db)):
    """Return the current site-wide default theme (admin only)."""
    theme_id = await _get_default_theme(db)
    if theme_id in DEFAULT_THEMES:
        return DEFAULT_THEMES[theme_id]
    return _custom_themes.get(theme_id, DEFAULT_THEMES["paper"])


@router.get("/default-info", response_model=ThemeDefaultInfo)
async def get_default_theme_info(current_user: str = Depends(get_current_user), db: AsyncSession = Depends(get_db)):
    """Return the site-wide default theme name and id. Accessible to all authenticated users."""
    theme_id = await _get_default_theme(db)
    if theme_id in DEFAULT_THEMES:
        theme = DEFAULT_THEMES[theme_id]
    else:
        theme = _custom_themes.get(theme_id, DEFAULT_THEMES["paper"])
    return ThemeDefaultInfo(id=theme.id, name=theme.name)


@router.delete("/personal", status_code=204)
async def clear_personal_theme(current_user: str = Depends(get_current_user), db: AsyncSession = Depends(get_db)):
    """Clear the current user's personal theme preference so they inherit the site default."""
    result = await db.execute(select(Person).where(Person.username == current_user))
    person = result.scalars().first()
    if person:
        person.preferred_theme = None
        db.add(person)
        await db.commit()


@router.put("/default/{theme_id}", response_model=ThemeOut)
async def set_default_theme(theme_id: str, current_user: str = Depends(require_admin), db: AsyncSession = Depends(get_db)):
    """Set the site-wide default theme (admin only)."""
    if theme_id not in DEFAULT_THEMES and theme_id not in _custom_themes:
        raise HTTPException(status_code=404, detail="Theme not found")
    await _set_default_theme(db, theme_id)
    if theme_id in DEFAULT_THEMES:
        return DEFAULT_THEMES[theme_id]
    return _custom_themes[theme_id]


@router.post("/set/{theme_id}", response_model=ThemeOut)
async def set_theme(theme_id: str, current_user: str = Depends(get_current_user), db: AsyncSession = Depends(get_db)):
    """Set the personal theme preference for the current user."""
    result = await db.execute(select(Person).where(Person.username == current_user))
    person = result.scalars().first()
    if person:
        person.preferred_theme = theme_id
        db.add(person)
        await db.commit()
        await db.refresh(person)

    if theme_id in DEFAULT_THEMES:
        return DEFAULT_THEMES[theme_id]
    return _custom_themes.get(theme_id, DEFAULT_THEMES["paper"])


@router.post("/save", response_model=ThemeOut)
async def save_custom_theme(body: ThemeSave, current_user: str = Depends(get_current_user), db: AsyncSession = Depends(get_db)):
    theme_id = f"custom_{len(_custom_themes)}"
    theme = ThemeOut(id=theme_id, name=body.name, colors=body.colors)
    _custom_themes[theme_id] = theme
    return theme


@router.patch("/update/{theme_id}", response_model=ThemeOut)
async def update_theme(theme_id: str, body: ThemeUpdate, current_user: str = Depends(get_current_user), db: AsyncSession = Depends(get_db)):
    if theme_id in DEFAULT_THEMES:
        raise HTTPException(status_code=400, detail="Cannot modify default themes")
    if theme_id not in _custom_themes:
        raise HTTPException(status_code=404, detail="Theme not found")

    theme = _custom_themes[theme_id]
    if body.name:
        theme.name = body.name
    if body.colors:
        theme.colors = body.colors

    _custom_themes[theme_id] = theme
    return theme


@router.patch("/rename/{theme_id}", response_model=ThemeOut)
async def rename_theme(theme_id: str, body: dict, current_user: str = Depends(get_current_user), db: AsyncSession = Depends(get_db)):
    if theme_id in DEFAULT_THEMES:
        raise HTTPException(status_code=400, detail="Cannot modify default themes")
    if theme_id not in _custom_themes:
        raise HTTPException(status_code=404, detail="Theme not found")

    if "name" not in body or not body["name"]:
        raise HTTPException(status_code=400, detail="Name is required")

    theme = _custom_themes[theme_id]
    theme.name = body["name"]
    _custom_themes[theme_id] = theme
    return theme


@router.delete("/delete/{theme_id}")
async def delete_theme(theme_id: str, current_user: str = Depends(get_current_user), db: AsyncSession = Depends(get_db)):
    if theme_id in DEFAULT_THEMES:
        raise HTTPException(status_code=400, detail="Cannot delete default themes")
    if theme_id not in _custom_themes:
        raise HTTPException(status_code=404, detail="Theme not found")
    del _custom_themes[theme_id]
    current_default = await _get_default_theme(db)
    if current_default == theme_id:
        await _set_default_theme(db, "dark")
    return {"message": "Theme deleted"}
