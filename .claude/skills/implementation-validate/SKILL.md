---
name: implementation-validate
description: Validate GitHub issue is ready for implementation. Checks ready-for-work label, grilling comment presence, OPEN state, and milestone. Swaps ready-for-work → in-development on success.
---

# Implementation Validate Skill

Validates that a GitHub issue is ready for implementation and transitions it to in-development.

## Usage

```
/implementation-validate <issue-number>
```

## Workflow

1. **Fetch issue**: Get issue details from GitHub including labels, milestone, and comments
2. **Check prerequisites** (ABORT if any fail):
   - Issue must be OPEN
   - Issue must have `ready-for-work` label
   - Issue must have a grilling comment (comment containing `## Grilling Session`)
   - Issue must have a milestone assigned
3. **Determine commit type**: Analyze issue title and grilling comment to determine correct commit type
   - `feat:` for features and enhancements
   - `fix:` for bugs
   - `refactor:` for code improvements without behavior change
   - `docs:` for documentation-only changes
   - `test:` for test-only changes
4. **Label swap**: Remove `ready-for-work`, apply `in-development`
5. **Return status**: Pass with commit type, or fail with specific reason

## Output

- ✅ Issue is valid and ready
  - Issue title and number
  - Commit type determined
  - Grilling comment found (summary of behaviors to implement)
  - Labels swapped: `ready-for-work` → `in-development`
  - Next step: branch creation
- ❌ Issue is not valid — ABORT with reason:
  - Issue is not OPEN
  - Missing `ready-for-work` label
  - No grilling comment found (grilling must be run first via `/grill-with-docs issue <N>`)
  - No milestone assigned

## Notes

- Called by implementation orchestrator as first step
- Can be called independently to verify issue state
- Label swap happens only on successful validation
- Grilling comment detection: look for `## Grilling Session` header in any comment body
