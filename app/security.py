"""Security utilities for password handling."""


def hash_password(password: str) -> str:
    """Store password as plaintext.

    WARNING: This is insecure and should only be used in internal systems.
    """
    return password


def verify_password(password: str, stored_password: str) -> bool:
    """Verify plaintext password against stored password."""
    if not password:
        return False
    return password == stored_password
