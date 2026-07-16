from __future__ import annotations

from datetime import date, datetime
from typing import Any, Literal, Optional

from pydantic import BaseModel, RootModel, field_validator, model_validator
import re
import zoneinfo


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


class PasswordResetRequired(BaseModel):
    """Returned as the body of a 403 when requires_password_reset is True."""
    reset_token: str
    detail: str = "Password change required"


class PasswordChangeRequest(BaseModel):
    old_password: str
    new_password: str

    @field_validator("new_password")
    @classmethod
    def validate_new_password(cls, v: str) -> str:
        if len(v) < 8:
            raise ValueError("Password must be at least 8 characters")
        return v


class PasswordResetRequest(BaseModel):
    new_password: str

    @field_validator("new_password")
    @classmethod
    def validate_new_password(cls, v: str) -> str:
        if len(v) < 8:
            raise ValueError("Password must be at least 8 characters")
        return v


# ── People ────────────────────────────────────────────────────────────────────

class PersonCreate(BaseModel):
    name: str
    username: str
    password: Optional[str] = None
    color: Optional[str] = None  # TODO: Remove color field in next major version

    @field_validator("name")
    @classmethod
    def validate_name(cls, v: str) -> str:
        v = v.strip()
        if not v:
            raise ValueError("name must not be empty")
        if len(v) > 100:
            raise ValueError("name must be 100 characters or fewer")
        return v

    @field_validator("username")
    @classmethod
    def validate_username(cls, v: str) -> str:
        v = v.strip()
        if not v:
            raise ValueError("username must not be empty")
        if len(v) > 50:
            raise ValueError("username must be 50 characters or fewer")
        if not re.match(r"^[a-z0-9_]+$", v):
            raise ValueError("username may only contain lowercase letters, digits, and underscores")
        return v

    @field_validator("password")
    @classmethod
    def validate_password(cls, v: Optional[str]) -> Optional[str]:
        if v is not None and len(v) < 8:
            raise ValueError("Password must be at least 8 characters")
        return v


class PersonUpdate(BaseModel):
    name: Optional[str] = None
    username: Optional[str] = None
    color: Optional[str] = None  # TODO: Remove color field in next major version
    goal_7d: Optional[int] = None
    goal_30d: Optional[int] = None
    is_admin: Optional[bool] = None
    preferred_theme: Optional[str] = None
    password: Optional[str] = None

    @field_validator("name")
    @classmethod
    def validate_name(cls, v: Optional[str]) -> Optional[str]:
        if v is not None:
            v = v.strip()
            if not v:
                raise ValueError("name must not be empty")
            if len(v) > 100:
                raise ValueError("name must be 100 characters or fewer")
        return v

    @field_validator("username")
    @classmethod
    def validate_username(cls, v: Optional[str]) -> Optional[str]:
        if v is not None:
            v = v.strip()
            if not v:
                raise ValueError("username must not be empty")
            if len(v) > 50:
                raise ValueError("username must be 50 characters or fewer")
            if not re.match(r"^[a-z0-9_]+$", v):
                raise ValueError("username may only contain lowercase letters, digits, and underscores")
        return v

    @field_validator("password")
    @classmethod
    def validate_password(cls, v: Optional[str]) -> Optional[str]:
        if v is not None and len(v) < 8:
            raise ValueError("Password must be at least 8 characters")
        return v


class PersonRedemption(BaseModel):
    amount: int


class PersonOut(BaseModel):
    id: int
    name: str
    username: str
    requires_password_reset: bool
    is_admin: bool
    color: str
    goal_7d: int
    goal_30d: int
    points: int
    points_redeemed: int
    preferred_theme: Optional[str] = None

    model_config = {"from_attributes": True}


class PersonRef(BaseModel):
    id: int
    name: str


# ── Chores ────────────────────────────────────────────────────────────────────

_VALID_SCHEDULE_TYPES = {"interval", "weekly", "monthly", "yearly"}
_VALID_ASSIGNMENT_TYPES = {"open", "fixed", "rotating"}


class ChoreCreate(BaseModel):
    name: str
    schedule_type: str
    schedule_config: dict[str, Any]
    assignment_type: str = "open"
    eligible_people: list[str] = []
    assignee: Optional[str] = None
    points: int = 0
    disabled: bool = False

    @field_validator("name")
    @classmethod
    def validate_name(cls, v: str) -> str:
        v = v.strip()
        if not v:
            raise ValueError("name must not be empty")
        if len(v) > 200:
            raise ValueError("name must be 200 characters or fewer")
        return v

    @field_validator("points")
    @classmethod
    def validate_points(cls, v: int) -> int:
        if v < 0:
            raise ValueError("points must be non-negative")
        return v

    @field_validator("schedule_type")
    @classmethod
    def validate_schedule_type(cls, v: str) -> str:
        if v not in _VALID_SCHEDULE_TYPES:
            raise ValueError(f"schedule_type must be one of: {', '.join(sorted(_VALID_SCHEDULE_TYPES))}")
        return v

    @field_validator("assignment_type")
    @classmethod
    def validate_assignment_type(cls, v: str) -> str:
        if v not in _VALID_ASSIGNMENT_TYPES:
            raise ValueError(f"assignment_type must be one of: {', '.join(sorted(_VALID_ASSIGNMENT_TYPES))}")
        return v

    @model_validator(mode="after")
    def validate_schedule_config(self) -> "ChoreCreate":
        _validate_schedule_config(self.schedule_type, self.schedule_config)
        return self


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

    @field_validator("name")
    @classmethod
    def validate_name(cls, v: Optional[str]) -> Optional[str]:
        if v is not None:
            v = v.strip()
            if not v:
                raise ValueError("name must not be empty")
            if len(v) > 200:
                raise ValueError("name must be 200 characters or fewer")
        return v

    @field_validator("points")
    @classmethod
    def validate_points(cls, v: Optional[int]) -> Optional[int]:
        if v is not None and v < 0:
            raise ValueError("points must be non-negative")
        return v

    @field_validator("schedule_type")
    @classmethod
    def validate_schedule_type(cls, v: Optional[str]) -> Optional[str]:
        if v is not None and v not in _VALID_SCHEDULE_TYPES:
            raise ValueError(f"schedule_type must be one of: {', '.join(sorted(_VALID_SCHEDULE_TYPES))}")
        return v

    @field_validator("assignment_type")
    @classmethod
    def validate_assignment_type(cls, v: Optional[str]) -> Optional[str]:
        if v is not None and v not in _VALID_ASSIGNMENT_TYPES:
            raise ValueError(f"assignment_type must be one of: {', '.join(sorted(_VALID_ASSIGNMENT_TYPES))}")
        return v

    @model_validator(mode="after")
    def validate_schedule_config(self) -> "ChoreUpdate":
        if self.schedule_type is not None and self.schedule_config is not None:
            _validate_schedule_config(self.schedule_type, self.schedule_config)
        return self


def _validate_schedule_config(schedule_type: str, config: dict[str, Any]) -> None:
    """Cross-field validation: schedule_config must be consistent with schedule_type."""
    if schedule_type == "interval":
        days = config.get("days")
        if days is None:
            raise ValueError("interval schedule_config requires 'days'")
        if not isinstance(days, int) or days < 1:
            raise ValueError("interval schedule_config 'days' must be a positive integer")
    elif schedule_type == "weekly":
        days = config.get("days")
        if days is None:
            raise ValueError("weekly schedule_config requires 'days'")
        if not isinstance(days, list) or not days:
            raise ValueError("weekly schedule_config 'days' must be a non-empty list of weekday integers")
    elif schedule_type == "monthly":
        if "day_of_month" not in config and "weekday_occurrence" not in config:
            raise ValueError("monthly schedule_config requires 'day_of_month' or 'weekday_occurrence'")
    elif schedule_type == "yearly":
        month = config.get("month")
        if month is None:
            raise ValueError("yearly schedule_config requires 'month'")
        if not isinstance(month, int) or not (1 <= month <= 12):
            raise ValueError("yearly schedule_config 'month' must be 1–12")
        if "day_of_month" not in config and "weekday_occurrence" not in config:
            raise ValueError("yearly schedule_config requires 'day_of_month' or 'weekday_occurrence'")


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


class PointAwardCreate(BaseModel):
    """Request body for a one-time admin point award (a Credit not tied to a Chore)."""
    person: str
    points: int
    reason: str

    @field_validator("person")
    @classmethod
    def validate_person(cls, v: str) -> str:
        if not v or not v.strip():
            raise ValueError("person is required")
        return v.strip()

    @field_validator("reason")
    @classmethod
    def validate_reason(cls, v: str) -> str:
        if not v or not v.strip():
            raise ValueError("reason is required")
        return v.strip()

    @field_validator("points")
    @classmethod
    def validate_points(cls, v: int) -> int:
        if v <= 0:
            raise ValueError("points must be positive")
        return v


class RedemptionLogOut(BaseModel):
    id: int
    person_id: int
    amount: int
    redeemed_by: str
    timestamp: datetime

    model_config = {"from_attributes": True}


class ChoreLogOut(BaseModel):
    id: int
    chore_id: int
    chore_name: str
    person: str
    action: str
    timestamp: datetime
    reassigned_to: Optional[str] = None
    assignee: Optional[str] = None
    field_name: Optional[str] = None
    old_value: Optional[str] = None
    new_value: Optional[str] = None

    model_config = {"from_attributes": True}


class UserLogOut(BaseModel):
    id: int
    chore_id: int
    chore_name: str
    person: str
    action: str
    timestamp: datetime
    reassigned_to: Optional[str] = None
    field_name: Optional[str] = None
    old_value: Optional[str] = None
    new_value: Optional[str] = None

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
    display_points: int
    points_7d: int
    points_30d: int
    completed_count: int
    skipped_count: int


# ── Config ───────────────────────────────────────────────────────────────────

class ConfigUpdate(BaseModel):
    title: Optional[str] = None
    auth_enabled: Optional[bool] = None
    timezone: Optional[str] = None
    due_soon_days: Optional[int] = None
    due_time_hour: Optional[int] = None
    update_check_enabled: Optional[bool] = None
    update_check_interval: Optional[int] = None

    @field_validator("timezone")
    @classmethod
    def validate_timezone(cls, v: Optional[str]) -> Optional[str]:
        if v is not None:
            try:
                zoneinfo.ZoneInfo(v)
            except (zoneinfo.ZoneInfoNotFoundError, KeyError):
                raise ValueError(f"Invalid timezone: {v!r}")
        return v

    @field_validator("title")
    @classmethod
    def validate_title(cls, v: Optional[str]) -> Optional[str]:
        if v is not None:
            v = v.strip()
            if not v:
                raise ValueError("title must not be empty")
            if len(v) > 100:
                raise ValueError("title must be 100 characters or fewer")
        return v

    @field_validator("due_soon_days")
    @classmethod
    def validate_due_soon_days(cls, v):
        if v is not None and (v < 1 or v > 365):
            raise ValueError("due_soon_days must be between 1 and 365")
        return v

    @field_validator("due_time_hour")
    @classmethod
    def validate_due_time_hour(cls, v):
        if v is not None and (v < 0 or v > 23):
            raise ValueError("due_time_hour must be between 0 and 23")
        return v

    @field_validator("update_check_interval")
    @classmethod
    def validate_update_check_interval(cls, v):
        if v is not None and v < 1:
            raise ValueError("update_check_interval must be at least 1 hour")
        return v


class ConfigOut(BaseModel):
    title: str
    auth_enabled: bool
    timezone: str
    due_soon_days: int
    due_time_hour: int
    update_check_enabled: bool
    update_check_interval: int


class UpdateCheckStatus(BaseModel):
    current_version: str
    latest_version: Optional[str] = None
    last_checked_at: Optional[datetime] = None
    # Next planned run of the periodic update-check job, so the configured
    # interval is observable alongside last_checked_at. Null when the scheduler
    # isn't running (e.g. under tests).
    next_scheduled_run: Optional[datetime] = None
    check_enabled: bool
    check_interval_hours: int
    update_available: bool = False

    model_config = {"from_attributes": True}


class VersionOut(BaseModel):
    """Public, unauthenticated self-version payload for GET /version.

    Same trust tier as /health — no admin/auth-gated fields (check_enabled,
    check_interval_hours) are exposed here, unlike UpdateCheckStatus.
    """
    version: str
    latest_version: Optional[str] = None
    update_available: bool = False
    checked_at: Optional[datetime] = None

    model_config = {"from_attributes": True}


# ── Auth Log ─────────────────────────────────────────────────────────────────

class AuthLogOut(BaseModel):
    id: int
    username: str
    action: str
    changed_by: Optional[str] = None
    timestamp: datetime

    model_config = {"from_attributes": True}


# ── Admin DB ─────────────────────────────────────────────────────────────────

class PointsLogUpdate(BaseModel):
    points: int
    person: str


class PointsLogAdminOut(PointsLogOut):
    pass


class AdminDbPage(BaseModel):
    items: list[PointsLogAdminOut]
    total: int
    offset: int
    limit: int


# ── Notifications ────────────────────────────────────────────────────────────

class NotificationOut(BaseModel):
    id: int
    person_id: int
    type: str
    chore_id: Optional[int] = None
    title: str
    body: str
    created_at: datetime
    delivered_at: Optional[datetime] = None
    acknowledged_at: Optional[datetime] = None
    dismissed_at: Optional[datetime] = None

    model_config = {"from_attributes": True}


class NotificationPreferencesOut(RootModel[dict[str, bool]]):
    """Per-type enablement map, e.g. ``{"chore_due": true}``.

    Every known notification type is present; a type with no stored
    NotificationPreference row is reported as ``true`` (absent = enabled).
    """


class NotificationPreferencesUpdate(RootModel[dict[str, bool]]):
    """Per-type enablement map accepted by ``PUT /notifications/preferences``.

    Same shape as :class:`NotificationPreferencesOut`; keys naming unknown
    types are ignored.
    """


# ── Theme ────────────────────────────────────────────────────────────────────

class ThemeColors(BaseModel):
    bg: str
    surface: str
    surface2: str
    accent: str
    primary: str
    secondary: str
    success: str
    warning: str
    error: str


class ThemeOut(BaseModel):
    id: str
    name: str
    colors: ThemeColors


class ThemeCurrentOut(ThemeOut):
    """Extended theme response for /theme/current that includes personal preference flag."""
    is_personal: bool


class ThemeDefaultInfo(BaseModel):
    """Lightweight default theme info accessible to all authenticated users."""
    id: str
    name: str


class ThemeSave(BaseModel):
    name: str
    colors: ThemeColors


class ThemeUpdate(BaseModel):
    name: Optional[str] = None
    colors: Optional[ThemeColors] = None
