"""Authentication routes."""
from datetime import datetime, date, timedelta, timezone
from typing import Optional
from fastapi import APIRouter, Depends, HTTPException, Header, Query
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
import uuid

from ..database import get_db
from ..models import Person, TokenBlacklist, AuthLog
from ..schemas import (
    LoginRequest, LoginResponse, UserInfo,
    PasswordChangeRequest, PasswordResetRequest, PasswordResetRequired,
    AuthLogOut,
)
from ..security import hash_password, verify_password
from ..config import settings
from ..dependencies import _decode_jwt_token, get_current_user, require_admin
from ..services.logging import log_auth_event

router = APIRouter(prefix="/auth", tags=["auth"])


@router.get("/setup-status")
async def setup_status(db: AsyncSession = Depends(get_db)):
    """Check if initial setup is needed (no users in database)."""
    result = await db.execute(select(Person))
    count = len(result.scalars().all())
    return {"setup_needed": count == 0}


def _create_jwt_token(username: str, is_admin: bool) -> str:
    """Create a JWT token for the given user."""
    try:
        from jose import jwt
    except ImportError:
        raise ImportError("python-jose is required for JWT support")

    payload = {
        "sub": username,
        "jti": str(uuid.uuid4()),  # JWT ID for token blacklisting
        "is_admin": is_admin,
        "exp": datetime.now(timezone.utc) + timedelta(days=365),
    }

    token = jwt.encode(payload, settings.jwt_secret, algorithm="HS256")
    return token


def _create_reset_jwt_token(username: str) -> str:
    """Create a short-lived reset JWT (15 min) for forced password reset flow."""
    try:
        from jose import jwt
    except ImportError:
        raise ImportError("python-jose is required for JWT support")

    payload = {
        "sub": username,
        "jti": str(uuid.uuid4()),
        "reset": True,  # marks this as a reset-only token
        "exp": datetime.now(timezone.utc) + timedelta(minutes=15),
    }

    token = jwt.encode(payload, settings.jwt_secret, algorithm="HS256")
    return token


@router.post("/login", response_model=LoginResponse, responses={403: {"model": PasswordResetRequired}})
async def login(body: LoginRequest, db: AsyncSession = Depends(get_db)):
    """Login with username and password.

    If no users exist in the database, the first login auto-creates the user as admin.
    Returns 403 with a short-lived reset token if the user must change their password.
    Logs login_succeeded or login_failed to auth_log.
    """
    # Check if user exists
    result = await db.execute(select(Person).where(Person.username == body.username))
    person = result.scalar_one_or_none()

    if person is None:
        # Check if this is the first user
        all_users = await db.execute(select(Person))
        user_count = len(all_users.scalars().all())

        if user_count == 0:
            # Auto-create first user as admin — no reset required for new account
            is_admin = True
            person = Person(
                name=body.username.capitalize(),
                username=body.username,
                password_hash=hash_password(body.password),
                is_admin=is_admin,
                requires_password_reset=False,
            )
            db.add(person)
            await log_auth_event(body.username, "user_created", db, changed_by="system")
            await db.commit()
            await db.refresh(person)
        else:
            # User doesn't exist and it's not the first user — always same message
            await log_auth_event(body.username, "login_failed", db)
            await db.commit()
            raise HTTPException(status_code=401, detail="Invalid username or password")
    else:
        # User exists, verify password
        if not verify_password(body.password, person.password_hash):
            await log_auth_event(body.username, "login_failed", db)
            await db.commit()
            raise HTTPException(status_code=401, detail="Invalid username or password")
        is_admin = person.is_admin

    # If a forced reset is required, return 403 with a short-lived reset token
    if person.requires_password_reset:
        reset_token = _create_reset_jwt_token(body.username)
        # Don't log login_succeeded here — success happens after reset
        raise HTTPException(
            status_code=403,
            detail=PasswordResetRequired(reset_token=reset_token).model_dump(),
        )

    # Log successful login
    await log_auth_event(body.username, "login_succeeded", db)
    await db.commit()

    # Generate normal JWT token
    token = _create_jwt_token(body.username, is_admin)

    return LoginResponse(
        access_token=token,
        token_type="bearer",
        user=UserInfo(username=body.username, is_admin=is_admin),
    )


@router.post("/logout", status_code=204)
async def logout(authorization: str = Header(None), db: AsyncSession = Depends(get_db)):
    """Logout by invalidating the JWT token."""
    if not authorization:
        raise HTTPException(status_code=401, detail="Missing authorization header")

    parts = authorization.split()
    if len(parts) != 2 or parts[0].lower() != "bearer":
        raise HTTPException(status_code=401, detail="Invalid authorization header")

    token = parts[1]
    payload = _decode_jwt_token(token)

    jti = payload.get("jti")
    exp = payload.get("exp")

    if not jti:
        raise HTTPException(status_code=401, detail="Invalid token")

    exp_datetime = datetime.fromtimestamp(exp, tz=timezone.utc)

    blacklist_entry = TokenBlacklist(
        token_jti=jti,
        invalidated_at=datetime.now(timezone.utc),
        expires_at=exp_datetime,
    )
    db.add(blacklist_entry)
    await db.commit()

    return None


@router.get("/me", response_model=UserInfo)
async def get_current_user_info(
    username: str = Depends(get_current_user),
    db: AsyncSession = Depends(get_db)
):
    """Get current authenticated user info."""
    result = await db.execute(select(Person).where(Person.username == username))
    person = result.scalar_one_or_none()

    if not person:
        raise HTTPException(status_code=401, detail="User not found")

    return UserInfo(username=person.username, is_admin=person.is_admin)


@router.put("/password")
async def change_password(
    body: PasswordChangeRequest,
    username: str = Depends(get_current_user),
    db: AsyncSession = Depends(get_db)
):
    """Change password for authenticated user (requires old password)."""
    if body.new_password == body.old_password:
        raise HTTPException(status_code=400, detail="New password must be different from old password")

    result = await db.execute(select(Person).where(Person.username == username))
    person = result.scalar_one_or_none()

    if not person:
        raise HTTPException(status_code=401, detail="User not found")

    if not verify_password(body.old_password, person.password_hash):
        raise HTTPException(status_code=401, detail="Invalid old password")

    person.password_hash = hash_password(body.new_password)
    db.add(person)
    await log_auth_event(username, "password_changed", db)
    await db.commit()

    return {"message": "Password changed successfully"}


@router.put("/password/reset")
async def reset_password(
    body: PasswordResetRequest,
    authorization: str = Header(None),
    db: AsyncSession = Depends(get_db),
):
    """Reset password using a short-lived reset token (no old password required).

    Accepts the reset token issued in the 403 response from POST /auth/login
    when requires_password_reset is True. Clears the flag on success and issues
    a normal JWT.
    """
    if not authorization:
        raise HTTPException(status_code=401, detail="Missing authorization header")

    parts = authorization.split()
    if len(parts) != 2 or parts[0].lower() != "bearer":
        raise HTTPException(status_code=401, detail="Invalid authorization header")

    token = parts[1]
    payload = _decode_jwt_token(token)

    # Verify this is a reset token
    if not payload.get("reset"):
        raise HTTPException(status_code=403, detail="Not a password reset token")

    username = payload.get("sub")
    if not username:
        raise HTTPException(status_code=401, detail="Invalid token")

    result = await db.execute(select(Person).where(Person.username == username))
    person = result.scalar_one_or_none()

    if not person:
        raise HTTPException(status_code=401, detail="User not found")

    person.password_hash = hash_password(body.new_password)
    person.requires_password_reset = False
    db.add(person)
    await log_auth_event(username, "password_reset", db)
    await db.commit()

    # Issue a normal JWT now that the reset is complete
    # Also log the successful login
    await log_auth_event(username, "login_succeeded", db)
    await db.commit()

    normal_token = _create_jwt_token(username, person.is_admin)
    return LoginResponse(
        access_token=normal_token,
        token_type="bearer",
        user=UserInfo(username=username, is_admin=person.is_admin),
    )


@router.get("/log", response_model=list[AuthLogOut])
async def get_auth_log(
    username: Optional[str] = Query(None),
    action: Optional[str] = Query(None),
    start_date: Optional[date] = Query(None),
    end_date: Optional[date] = Query(None),
    current_user: str = Depends(require_admin),
    db: AsyncSession = Depends(get_db),
):
    """Get auth event log. Admin only.

    Filter by username, action (login_succeeded, login_failed, password_changed,
    password_reset, user_created), start_date, end_date.
    """
    query = select(AuthLog).order_by(AuthLog.timestamp.desc())

    if username:
        query = query.where(AuthLog.username.ilike(username))
    if action:
        query = query.where(AuthLog.action == action)
    if start_date:
        query = query.where(AuthLog.timestamp >= datetime.combine(start_date, datetime.min.time()))
    if end_date:
        query = query.where(AuthLog.timestamp <= datetime.combine(end_date, datetime.max.time()))

    result = await db.execute(query)
    return result.scalars().all()
