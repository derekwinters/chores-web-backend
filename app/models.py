from datetime import date, datetime
from typing import Optional

from sqlalchemy import Integer, Text, Date, DateTime, JSON, Boolean
from sqlalchemy.orm import DeclarativeBase, Mapped, mapped_column


class Base(DeclarativeBase):
    pass


class Person(Base):
    __tablename__ = "people"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    name: Mapped[str] = mapped_column(Text, nullable=False)
    username: Mapped[str] = mapped_column(Text, unique=True, nullable=False)
    password_hash: Mapped[str] = mapped_column(Text, nullable=False)
    is_admin: Mapped[bool] = mapped_column(Integer, nullable=False, default=False)
    color: Mapped[str] = mapped_column(Text, nullable=False, default="#004272")
    goal_7d: Mapped[int] = mapped_column(Integer, nullable=False, default=20)
    goal_30d: Mapped[int] = mapped_column(Integer, nullable=False, default=80)
    points: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    preferred_theme: Mapped[Optional[str]] = mapped_column(Text, nullable=True)


class TokenBlacklist(Base):
    __tablename__ = "token_blacklist"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    token_jti: Mapped[str] = mapped_column(Text, unique=True, nullable=False)
    invalidated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    expires_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)


class Chore(Base):
    __tablename__ = "chores"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    name: Mapped[str] = mapped_column(Text, nullable=False)

    # Schedule config stored as JSON (JSONB in Postgres, TEXT-backed in SQLite)
    schedule_type: Mapped[str] = mapped_column(Text, nullable=False)
    schedule_config: Mapped[dict] = mapped_column(JSON, nullable=False, default=dict)

    assignment_type: Mapped[str] = mapped_column(Text, nullable=False, default="open")
    eligible_people: Mapped[list] = mapped_column(JSON, nullable=False, default=list)
    assignee: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    points: Mapped[int] = mapped_column(Integer, nullable=False, default=0)

    # Runtime state
    state: Mapped[str] = mapped_column(Text, nullable=False, default="due")
    disabled: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False)
    next_due: Mapped[Optional[date]] = mapped_column(Date, nullable=True)
    current_assignee: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    rotation_index: Mapped[int] = mapped_column(Integer, nullable=False, default=0)

    last_changed_at: Mapped[Optional[datetime]] = mapped_column(DateTime(timezone=True), nullable=True)
    last_changed_by: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    last_change_type: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    last_completed_at: Mapped[Optional[datetime]] = mapped_column(DateTime(timezone=True), nullable=True)
    last_completed_by: Mapped[Optional[str]] = mapped_column(Text, nullable=True)


class PointsLog(Base):
    __tablename__ = "points_log"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    person: Mapped[str] = mapped_column(Text, nullable=False)
    points: Mapped[int] = mapped_column(Integer, nullable=False)
    chore_id: Mapped[int] = mapped_column(Integer, nullable=False)
    completed_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)


class ChoreLog(Base):
    __tablename__ = "chore_log"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    chore_id: Mapped[int] = mapped_column(Integer, nullable=False)
    chore_name: Mapped[str] = mapped_column(Text, nullable=False)
    person: Mapped[str] = mapped_column(Text, nullable=False)
    action: Mapped[str] = mapped_column(Text, nullable=False)
    timestamp: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    reassigned_to: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    field_name: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    old_value: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    new_value: Mapped[Optional[str]] = mapped_column(Text, nullable=True)


class Settings(Base):
    __tablename__ = "settings"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    key: Mapped[str] = mapped_column(Text, unique=True, nullable=False)
    value: Mapped[str] = mapped_column(Text, nullable=False)
