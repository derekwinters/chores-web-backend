"""Authentication dependencies for FastAPI routes."""
from fastapi import Depends, HTTPException, Header
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from .database import get_db
from .models import Person, TokenBlacklist, Settings
from .config import settings


def _decode_jwt_token(token: str) -> dict:
    """Decode a JWT token and return its payload."""
    try:
        from jose import jwt, JWTError
    except ImportError:
        raise ImportError("python-jose is required for JWT support")

    try:
        payload = jwt.decode(token, settings.jwt_secret, algorithms=["HS256"])
        return payload
    except JWTError:
        raise HTTPException(status_code=401, detail="Invalid token")


async def get_current_user(authorization: str = Header(None), db: AsyncSession = Depends(get_db)) -> str:
    """Extract and validate JWT token from Authorization header.

    Returns the username if token is valid and not blacklisted.
    If auth is disabled globally, returns anonymous user.
    Raises 401 if token is missing, invalid, expired, or blacklisted (when auth enabled).
    """
    result = await db.execute(select(Settings).where(Settings.key == "auth_enabled"))
    settings_row = result.scalar_one_or_none()
    auth_enabled = settings_row and settings_row.value.lower() == "true"

    if not auth_enabled:
        return "anonymous"

    if not authorization:
        raise HTTPException(status_code=401, detail="Missing authorization header")

    parts = authorization.split()
    if len(parts) != 2 or parts[0].lower() != "bearer":
        raise HTTPException(status_code=401, detail="Invalid authorization header")

    token = parts[1]
    payload = _decode_jwt_token(token)

    username = payload.get("sub")
    jti = payload.get("jti")

    if not username or not jti:
        raise HTTPException(status_code=401, detail="Invalid token")

    result = await db.execute(select(TokenBlacklist).where(TokenBlacklist.token_jti == jti))
    blacklisted = result.scalar_one_or_none()

    if blacklisted:
        raise HTTPException(status_code=401, detail="Token has been revoked")

    return username


async def require_admin(username: str = Depends(get_current_user), db: AsyncSession = Depends(get_db)) -> str:
    """Verify that current user is admin.

    Returns the username if user is admin.
    Raises 403 if user is not admin.
    """
    result = await db.execute(select(Settings).where(Settings.key == "auth_enabled"))
    settings_row = result.scalar_one_or_none()
    auth_enabled = settings_row and settings_row.value.lower() == "true"

    if not auth_enabled:
        return username

    result = await db.execute(select(Person).where(Person.username == username))
    person = result.scalar_one_or_none()

    if not person or not person.is_admin:
        raise HTTPException(status_code=403, detail="Admin access required")

    return username
