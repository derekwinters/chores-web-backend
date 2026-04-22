"""Tests for TokenBlacklist model."""
import pytest
from datetime import datetime, timedelta
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models import TokenBlacklist


@pytest.mark.asyncio
async def test_token_blacklist_created(db: AsyncSession):
    """Verify TokenBlacklist can be created."""
    now = datetime.utcnow()
    expires = now + timedelta(days=365)

    blacklist = TokenBlacklist(token_jti="test_jti_123", invalidated_at=now, expires_at=expires)
    db.add(blacklist)
    await db.commit()
    await db.refresh(blacklist)

    assert blacklist.id is not None
    assert blacklist.token_jti == "test_jti_123"
    assert blacklist.invalidated_at is not None
    assert blacklist.expires_at is not None


@pytest.mark.asyncio
async def test_token_jti_uniqueness(db: AsyncSession):
    """Verify token_jti is unique."""
    now = datetime.utcnow()
    expires = now + timedelta(days=365)

    blacklist1 = TokenBlacklist(token_jti="jti_1", invalidated_at=now, expires_at=expires)
    db.add(blacklist1)
    await db.commit()

    blacklist2 = TokenBlacklist(token_jti="jti_1", invalidated_at=now, expires_at=expires)
    db.add(blacklist2)

    with pytest.raises(Exception):  # IntegrityError
        await db.commit()


@pytest.mark.asyncio
async def test_token_blacklist_query(db: AsyncSession):
    """Verify TokenBlacklist can be queried."""
    now = datetime.utcnow()
    expires = now + timedelta(days=365)

    blacklist = TokenBlacklist(token_jti="query_test_jti", invalidated_at=now, expires_at=expires)
    db.add(blacklist)
    await db.commit()

    result = await db.execute(select(TokenBlacklist).where(TokenBlacklist.token_jti == "query_test_jti"))
    found = result.scalar_one_or_none()

    assert found is not None
    assert found.token_jti == "query_test_jti"
