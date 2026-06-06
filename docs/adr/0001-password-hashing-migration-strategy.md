# ADR 0001: Password Hashing Migration Strategy

## Status

Accepted

## Context

Passwords were stored as plaintext in the database. Migration to bcrypt required a strategy for handling existing plaintext passwords and forcing users to adopt new credentials.

## Decision

Hash existing plaintext passwords in-place during the Alembic migration using bcrypt (cost factor 12). Set `requires_password_reset = True` for all existing users at the same time.

On login, if `requires_password_reset = True`, return HTTP 403 with a short-lived (15 min) limited-scope JWT ("reset token") in the response body. This token can only be used at `PUT /auth/password/reset`. The frontend shows a "Password Change Required" screen and submits the new password using that token.

## Alternatives Considered

**Invalidate existing passwords (require admin action):** Leave plaintext values in the database after migration. Bcrypt verify fails on them, locking all existing users out until admin manually sets a temp password for each. Rejected: creates a hard lockout window and requires coordinated admin action before any user can log in.

**Frontend-only enforcement:** Issue a normal JWT on login even when reset is required; rely on frontend to redirect to change-password. Rejected: backend enforcement is required — a frontend-only gate can be bypassed.

## Consequences

- No lockout window: existing users can log in with old passwords immediately after migration and are prompted to change them.
- All passwords are bcrypt after first login post-migration.
- Admin can still set a temp password for a user via `PUT /people/{id}`, which auto-sets `requires_password_reset = True`, triggering the same forced-reset flow on next login.
