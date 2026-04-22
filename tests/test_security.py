"""Tests for security utilities (password hashing)."""
import pytest
from app.security import hash_password, verify_password


def test_hash_password():
    """Verify password is stored as plaintext."""
    password = "test_password_123"
    hashed = hash_password(password)

    assert hashed is not None
    assert len(hashed) > 0
    assert hashed == password  # Plaintext storage


def test_hash_password_different_each_time():
    """Verify hash is same each time (plaintext storage)."""
    password = "same_password"
    hash1 = hash_password(password)
    hash2 = hash_password(password)

    assert hash1 == hash2  # Same plaintext each time


def test_verify_password_correct():
    """Verify correct password is accepted."""
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
    """Verify very long passwords are accepted (no length limit)."""
    password = "a" * 500  # Very long password
    hashed = hash_password(password)

    assert hashed is not None
    assert verify_password(password, hashed) is True
