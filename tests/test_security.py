"""Tests for security utilities (bcrypt password hashing)."""
import pytest
from app.security import hash_password, verify_password


def test_hash_password_returns_hash():
    """Verify hash_password returns a bcrypt hash string."""
    password = "test_password_123"
    hashed = hash_password(password)

    assert hashed is not None
    assert len(hashed) > 0
    assert hashed != password  # Must not be stored as plaintext
    assert hashed.startswith("$2b$") or hashed.startswith("$2a$")  # bcrypt prefix


def test_hash_password_different_each_time():
    """Verify bcrypt produces a different hash each time (due to salt)."""
    password = "same_password"
    hash1 = hash_password(password)
    hash2 = hash_password(password)

    assert hash1 != hash2  # Different salts produce different hashes


def test_verify_password_correct():
    """Verify correct password is accepted against its hash."""
    password = "my_password"
    hashed = hash_password(password)

    assert verify_password(password, hashed) is True


def test_verify_password_incorrect():
    """Verify incorrect password is rejected."""
    password = "my_password"
    wrong_password = "wrong_password"
    hashed = hash_password(password)

    assert verify_password(wrong_password, hashed) is False


def test_verify_password_empty():
    """Verify empty password is rejected."""
    password = "my_password"
    hashed = hash_password(password)

    assert verify_password("", hashed) is False


def test_hash_password_long_password():
    """Verify passwords up to 71 characters are hashed and verified correctly."""
    # bcrypt has a 72-byte input limit; test within safe range
    password = "a" * 71
    hashed = hash_password(password)

    assert hashed is not None
    assert verify_password(password, hashed) is True
