---
name: implementation-verify
description: Verify the backend test suite and API contract, then show changes summary for user review
---

# Implementation Verify Skill

Runs the test suite and the API-contract check to verify the change is sound, then shows a summary of changes for user review.

## Usage

```
/implementation-verify <issue-number>
```

## Workflow

1. **Run tests**: `pytest` (config in `pytest.ini`: `asyncio_mode = auto`, `testpaths = tests`)
2. **Regenerate the OpenAPI schema and check for contract drift**:
   - `python scripts/generate_openapi.py --output <tmp>/openapi.json`
   - Diff `<tmp>/openapi.json` against the golden snapshot in the `chores-web-docs` clone (`docs/api/openapi.json`).
   - If they differ, flag it: a change to the live schema means the contract in `chores-web-docs` must be updated (and, for breaking changes, `API_VERSION` incremented) — see CLAUDE.md's Breaking Change Ritual. Report the drift so the user can decide.
3. **Alembic-migration reminder**: if this change touched `app/models.py`, confirm a matching migration exists in `alembic/versions/` (`python -m alembic revision --autogenerate -m "..."` — see `MIGRATIONS.md`). A model change with no new revision is a defect — flag it.
4. **Verify success**: Check exit codes, report any test failures or contract drift.
5. **Prepare changes summary**:
   - List all files modified
   - Show line change counts
   - Summarize implementation
   - Display test results
6. **Pause workflow**: Wait for user approval or request for changes

## Parameters

- `issue_number` (optional): For reference in output

## Output

Shows:
- Files modified with line counts
- Implementation summary
- Test results
- API contract status (in sync / drift detected)
- Migration status (if `app/models.py` changed)
- Ready for user to:
  - Approve for commit
  - Request more changes
  - Abort

## Notes

- Called by orchestrator after tests pass
- Contract check confirms the live schema still matches the published golden snapshot
- Shows all changes before user reviews
- User has control point here
