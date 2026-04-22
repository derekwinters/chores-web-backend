from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from ..database import get_db
from ..models import Person
from ..schemas import ThemeOut, ThemeSave, ThemeColors
from ..dependencies import get_current_user

router = APIRouter(prefix="/theme", tags=["theme"])

# Default themes
DEFAULT_THEMES = {
    "dark": ThemeOut(
        id="dark",
        name="Dark",
        colors=ThemeColors(
            bg="#080c14",
            surface="#16202e",
            surface2="#1e2d40",
            accent="#73B1DD",
            success="#3db87a",
            warning="#e8a930",
            danger="#e05c6a",
        ),
    ),
    "light": ThemeOut(
        id="light",
        name="Light",
        colors=ThemeColors(
            bg="#f5f5f5",
            surface="#ffffff",
            surface2="#eeeeee",
            accent="#0066cc",
            success="#00aa00",
            warning="#ff9900",
            danger="#cc0000",
        ),
    ),
    "charcoal": ThemeOut(
        id="charcoal",
        name="Charcoal",
        colors=ThemeColors(
            bg="#1a1a1a",
            surface="#2d2d2d",
            surface2="#3a3a3a",
            accent="#999999",
            success="#999999",
            warning="#999999",
            danger="#999999",
        ),
    ),
    "paper": ThemeOut(
        id="paper",
        name="Paper",
        colors=ThemeColors(
            bg="#faf8f3",
            surface="#ffffff",
            surface2="#f0ede6",
            accent="#b8860b",
            success="#558b2f",
            warning="#e0860b",
            danger="#d32f2f",
        ),
    ),
    "pink": ThemeOut(
        id="pink",
        name="Pink",
        colors=ThemeColors(
            bg="#fce4ec",
            surface="#f8bbd0",
            surface2="#f48fb1",
            accent="#ec407a",
            success="#66bb6a",
            warning="#ffa726",
            danger="#ef5350",
        ),
    ),
    "frog": ThemeOut(
        id="frog",
        name="Frog",
        colors=ThemeColors(
            bg="#1b4d2e",
            surface="#2d6a3e",
            surface2="#3d8b52",
            accent="#c8e6c9",
            success="#9ccc65",
            warning="#ffa726",
            danger="#ef5350",
        ),
    ),
}

# Custom themes (in-memory, would be database in production)
_custom_themes: dict = {}
_current_theme = "dark"


@router.get("/list", response_model=list[ThemeOut])
async def list_themes(current_user: str = Depends(get_current_user), db: AsyncSession = Depends(get_db)):
    themes = list(DEFAULT_THEMES.values()) + list(_custom_themes.values())
    return themes


@router.get("/current", response_model=ThemeOut)
async def get_current_theme(current_user: str = Depends(get_current_user), db: AsyncSession = Depends(get_db)):
    result = await db.execute(select(Person).where(Person.username == current_user))
    person = result.scalars().first()

    theme_id = person.preferred_theme if person and person.preferred_theme else _current_theme
    if theme_id in DEFAULT_THEMES:
        return DEFAULT_THEMES[theme_id]
    return _custom_themes.get(theme_id, DEFAULT_THEMES["dark"])


@router.post("/set/{theme_id}", response_model=ThemeOut)
async def set_theme(theme_id: str, current_user: str = Depends(get_current_user), db: AsyncSession = Depends(get_db)):
    global _current_theme
    _current_theme = theme_id

    result = await db.execute(select(Person).where(Person.username == current_user))
    person = result.scalars().first()
    if person:
        person.preferred_theme = theme_id
        db.add(person)
        await db.commit()
        await db.refresh(person)

    if theme_id in DEFAULT_THEMES:
        return DEFAULT_THEMES[theme_id]
    return _custom_themes.get(theme_id, DEFAULT_THEMES["dark"])


@router.post("/save", response_model=ThemeOut)
async def save_custom_theme(body: ThemeSave, current_user: str = Depends(get_current_user), db: AsyncSession = Depends(get_db)):
    theme_id = f"custom_{len(_custom_themes)}"
    theme = ThemeOut(id=theme_id, name=body.name, colors=body.colors)
    _custom_themes[theme_id] = theme
    return theme


@router.delete("/delete/{theme_id}")
async def delete_theme(theme_id: str, current_user: str = Depends(get_current_user), db: AsyncSession = Depends(get_db)):
    global _current_theme
    if theme_id in DEFAULT_THEMES:
        raise HTTPException(status_code=400, detail="Cannot delete default themes")
    if theme_id not in _custom_themes:
        raise HTTPException(status_code=404, detail="Theme not found")
    del _custom_themes[theme_id]
    if _current_theme == theme_id:
        _current_theme = "dark"
    return {"message": "Theme deleted"}
