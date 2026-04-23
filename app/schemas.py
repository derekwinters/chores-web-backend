from __future__ import annotations

from datetime import date, datetime
from typing import Any, Optional

from pydantic import BaseModel, field_validator
import re


def _slugify(name: str) -> str:
    return re.sub(r"[^a-z0-9]+", "_", name.lower()).strip("_")


# ── Auth ──────────────────────────────────────────────────────────────────────

class LoginRequest(BaseModel):
    username: str
    password: str


class UserInfo(BaseModel):
    username: str
    is_admin: bool


class LoginResponse(BaseModel):
    access_token: str
    token_type: str
    user: UserInfo


class PasswordChangeRequest(BaseModel):
    old_password: str
    new_password: str


# ── People ────────────────────────────────────────────────────────────────────

class PersonCreate(BaseModel):
    name: str
    username: str
    password: Optional[str] = None
    color: Optional[str] = None


class PersonUpdate(BaseModel):
    name: Optional[str] = None
    username: Optional[str] = None
    color: Optional[str] = None
    goal_7d: Optional[int] = None
    goal_30d: Optional[int] = None
    is_admin: Optional[bool] = None
    preferred_theme: Optional[str] = None
    password: Optional[str] = None


class PersonOut(BaseModel):
    id: int
    name: str
    username: str
    is_admin: bool
    color: str
    goal_7d: int
    goal_30d: int
    preferred_theme: Optional[str] = None

    model_config = {"from_attributes": True}


class PersonRef(BaseModel):
    id: int
    name: str


# ── Chores ────────────────────────────────────────────────────────────────────

class ChoreCreate(BaseModel):
    name: str
    schedule_type: str
    schedule_config: dict[str, Any]
    assignment_type: str = "open"
    eligible_people: list[str] = []
    assignee: Optional[str] = None
    points: int = 0
    disabled: bool = False


class ChoreUpdate(BaseModel):
    name: Optional[str] = None
    schedule_type: Optional[str] = None
    schedule_config: Optional[dict[str, Any]] = None
    assignment_type: Optional[str] = None
    eligible_people: Optional[list[str]] = None
    assignee: Optional[str] = None
    current_assignee: Optional[str] = None
    next_assignee: Optional[str] = None
    points: Optional[int] = None
    disabled: Optional[bool] = None
    next_due: Optional[date] = None


class ChoreOut(BaseModel):
    id: int
    name: str
    schedule_type: str
    schedule_config: dict[str, Any]
    assignment_type: str
    eligible_people: list[str]
    assignee: Optional[str]
    points: int
    state: str
    disabled: bool
    next_due: Optional[date]
    current_assignee: Optional[str]
    rotation_index: int
    last_changed_at: Optional[datetime]
    last_changed_by: Optional[str]
    last_change_type: Optional[str]
    last_completed_at: Optional[datetime]
    last_completed_by: Optional[str]
    # computed
    age: Optional[int] = None
    schedule_summary: Optional[str] = None
    next_assignee: Optional[str] = None

    model_config = {"from_attributes": True}


# ── Actions ───────────────────────────────────────────────────────────────────

class CompleteBody(BaseModel):
    completed_by: Optional[str] = None


class SkipReassignBody(BaseModel):
    assignee: Optional[str] = None


class ReassignBody(BaseModel):
    assignee: str


# ── Points ────────────────────────────────────────────────────────────────────

class PointsLogOut(BaseModel):
    id: int
    person: str
    points: int
    chore_id: int
    completed_at: datetime

    model_config = {"from_attributes": True}


class ChoreLogOut(BaseModel):
    id: int
    chore_id: int
    chore_name: str
    person: str
    action: str
    timestamp: datetime
    reassigned_to: Optional[str] = None

    model_config = {"from_attributes": True}


class LeaderboardEntry(BaseModel):
    person: str
    total_points: int


class PointsSummaryEntry(BaseModel):
    person: str
    points_7d: int
    points_30d: int


class UserStatsOut(BaseModel):
    name: str
    total_points: int
    points_7d: int
    points_30d: int
    completed_count: int
    skipped_count: int


# ── Config ───────────────────────────────────────────────────────────────────

class ConfigUpdate(BaseModel):
    title: Optional[str] = None
    auth_enabled: Optional[bool] = None


class ConfigOut(BaseModel):
    title: str
    auth_enabled: bool


# ── Theme ────────────────────────────────────────────────────────────────────

class ThemeColors(BaseModel):
    bg: str
    surface: str
    surface2: str
    accent: str
    success: str
    warning: str
    danger: str


class ThemeOut(BaseModel):
    id: str
    name: str
    colors: ThemeColors


class ThemeSave(BaseModel):
    name: str
    colors: ThemeColors
