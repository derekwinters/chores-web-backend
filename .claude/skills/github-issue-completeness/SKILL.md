---
name: github-issue-completeness
description: Aggregate the triage validators' feedback into a single consolidated comment requesting missing information from the issue author. Engine skill called by the triage orchestrator.
---

<what-to-do>

## Invocation

```
/github-issue-completeness <issue-number>
```

Engine skill (not an orchestrator). Consolidates the validators' output into one user-facing request instead of many separate comments.

## Process

1. Take the validation output already gathered by the orchestrator (missing fields, questionable N/As, suggestions from the type-specific validator).
2. Group the gaps into:
   - **Required to proceed** — strict missing fields that block validation.
   - **Would be helpful** — nice-to-haves that improve the issue but do not block.
   - **Follow-up questions** — clarifications needed from the author.
3. Produce a single respectful Markdown comment the orchestrator can post to the issue.

## Output

A Markdown comment with the three sections above (Required to proceed / Would be helpful / Follow-up questions). Consolidates all validator feedback into one request rather than posting separate comments per validator.

</what-to-do>
