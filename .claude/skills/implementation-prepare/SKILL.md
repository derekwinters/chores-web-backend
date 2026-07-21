---
name: implementation-prepare
description: Prepare the caller-supplied git branch for implementation. Never invents a branch name.
---

# Implementation Prepare Skill

Prepares the git branch for issue implementation. Called by the orchestrator
after validation.

## Usage

```
/implementation-prepare <issue-number> <commit-type> <branch>
```

## Workflow

1. **Fetch main:** `git fetch origin && git checkout main && git pull origin main`.
2. **Checkout the given branch:**
   - If `<branch>` already exists locally or on `origin`, check it out — the
     shared-branch case (e.g. milestone mode).
   - Otherwise create it fresh from updated `main`: `git checkout -b <branch>`.
3. **Verify:** `git branch --show-current`.
4. **Report:** branch name and readiness.

## Parameters

- `issue_number` (required).
- `commit_type` (required): feat | fix | refactor | docs | test.
- `branch` (required): the exact branch name to prepare. **This skill never
  invents or derives a branch name — the caller always supplies one.**

## Alembic-migration reminder
If the change will touch `app/models.py`, add a matching Alembic revision
under `alembic/versions/` (`python -m alembic revision --autogenerate -m "..."`,
see `MIGRATIONS.md`). A schema change with no migration is incomplete and is
flagged at verify.


## Notes

- Idempotent for the shared-branch case: re-checking-out an existing branch is
  not a failure.
