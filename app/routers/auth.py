"""Authentication routes."""
from datetime import datetime, timedelta, timezone
from fastapi import APIRouter, Depends, HTTPException, Header
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
import uuid

from ..database import get_db
from ..models import Person, TokenBlacklist
from ..schemas import LoginRequest, LoginResponse, UserInfo, PasswordChangeRequest
from ..security import hash_password, verify_password
from ..config import settings
from ..dependencies import _decode_jwt_token, get_current_user

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


@router.post("/login", response_model=LoginResponse)
async def login(body: LoginRequest, db: AsyncSession = Depends(get_db)):
    """Login with username and password.

    If no users exist in the database, the first login auto-creates the user as admin.
    """
    # Check if user exists
    result = await db.execute(select(Person).where(Person.username == body.username))
    person = result.scalar_one_or_none()

    if person is None:
        # Check if this is the first user
        all_users = await db.execute(select(Person))
        user_count = len(all_users.scalars().all())

        if user_count == 0:
            # Auto-create first user as admin
            is_admin = True
            person = Person(
                name=body.username.capitalize(),
                username=body.username,
                password_hash=hash_password(body.password),
                is_admin=is_admin,
            )
            db.add(person)
            await db.commit()
            await db.refresh(person)
        else:
            # User doesn't exist and it's not the first user
            raise HTTPException(status_code=401, detail="Invalid username or password")
    else:
        # User exists, verify password
        if not verify_password(body.password, person.password_hash):
            raise HTTPException(status_code=401, detail="Invalid username or password")
        is_admin = person.is_admin

    # Generate JWT token
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
    """Change password for authenticated user."""
    if body.new_password == body.old_password:
        raise HTTPException(status_code=400, detail="New password must be different from old password")

    if len(body.new_password) < 8:
        raise HTTPException(status_code=400, detail="Password must be at least 8 characters")

    result = await db.execute(select(Person).where(Person.username == username))
    person = result.scalar_one_or_none()

    if not person:
        raise HTTPException(status_code=401, detail="User not found")

    if not verify_password(body.old_password, person.password_hash):
        raise HTTPException(status_code=401, detail="Invalid old password")

    person.password_hash = hash_password(body.new_password)
    db.add(person)
    await db.commit()

    return {"message": "Password changed successfully"}
