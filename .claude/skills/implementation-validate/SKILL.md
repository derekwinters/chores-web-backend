---
name: implementation-validate
description: Validate a GitHub issue is ready for implementation, then swap ready-for-work → in-development.
---

# Implementation Validate Skill

Validates that a GitHub issue is ready for implementation and transitions it to
`in-development`. Called by the implementation orchestrator as its first step.

## Usage

```
/implementation-validate <issue-number>
```

## Workflow

1. **Fetch issue:** labels, milestone, comments.
2. **Check prerequisites** (ABORT if any fail):
   - Issue is OPEN.
   - Issue has the `ready-for-work` label.
   - Issue has a grilling comment (a comment containing `## Grilling Session`) —
     grilling must be run first via `/grill-with-docs issue <N>`.
   - Issue has a milestone assigned.
3. **Determine commit type** from the title + grilling comment: `feat` (features/
   enhancements), `fix` (bugs), `refactor`, `docs`, `test`.
4. **Label swap:** remove `ready-for-work`, apply `in-development`.
5. **Return status:** pass with commit type, or fail with the specific reason.

## Notes

- The label swap happens only on successful validation.
- Grilling-comment detection: look for the `## Grilling Session` header in any
  comment body.
