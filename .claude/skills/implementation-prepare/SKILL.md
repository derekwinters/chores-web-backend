---
name: implementation-prepare
description: Prepare git branch for implementation
---

# Implementation Prepare Skill

Prepares git branch and environment for issue implementation.

## Usage

```
/implementation-prepare <issue-number> <commit-type> <branch>
```

## Workflow

1. **Fetch main branch**: `git fetch origin && git checkout main && git pull origin main`
2. **Checkout the given branch**:
   - If `<branch>` already exists locally or on `origin`, check it out (`git checkout <branch>` / `git checkout -b <branch> origin/<branch>`) — this is the shared-branch case (e.g. milestone mode).
   - Otherwise, create it fresh from updated `main`: `git checkout -b <branch>`.
3. **Verify branch is current**: `git branch --show-current`
4. **Report status**: Show branch name and readiness

## Parameters

- `issue_number` (required): GitHub issue number
- `commit_type` (required): Type of commit (feat, fix, refactor, docs, test)
- `branch` (required): The exact branch name to prepare. This skill never invents or derives a branch name — the caller always supplies one explicitly.
  - Standalone invocation: caller passes a self-chosen name (e.g. `<type>-issue-<number>`).
  - Milestone-mode invocation: caller passes the shared milestone branch (e.g. `claude/milestone-<number>-<randomid>`), owned and created by the milestone orchestrator.

## Output

- Branch name checked out/created: `<branch>`
- Branch status: Active and ready for implementation
- Next step: Begin implementation

## Notes

- Called by orchestrator after validation
- Can be called independently to prepare a branch
- Never composes a branch name itself — `<branch>` is always caller-supplied
- Idempotent for the shared-branch case: re-checking-out an existing branch is not a failure

## Alembic-migration reminder

If the planned change will touch `app/models.py`, the implementation must add a
matching Alembic revision under `alembic/versions/`
(`python -m alembic revision --autogenerate -m "..."` — see `MIGRATIONS.md`). Keep
this in view from the start: a schema change with no migration is an incomplete
change and will be flagged at verify.
