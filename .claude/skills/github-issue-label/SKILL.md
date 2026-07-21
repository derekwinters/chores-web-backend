---
name: github-issue-label
description: Apply, create, and remove labels on a GitHub issue idempotently from an explicit instruction set. Engine skill (not an orchestrator) that receives label data from the triage orchestrator.
---

<what-to-do>

## Invocation

Called by the orchestrator with an explicit label plan (not typically run by hand):

```json
{
  "issue_number": 123,
  "labels_to_apply": ["bug", "needs-info"],
  "labels_to_remove": [],
  "labels_to_keep": []
}
```

## Process

1. Read the current labels: `gh issue view <issue_number> --json labels`.
2. Create any label in `labels_to_apply` that does not exist yet (`gh label create`).
3. Apply `labels_to_apply` and remove `labels_to_remove` (`gh issue edit <issue_number> --add-label ... --remove-label ...`).
4. Leave `labels_to_keep` untouched.
5. Operate idempotently — re-running with the same input produces no further change.

## Output

```json
{
  "labels_applied": ["bug", "needs-info"],
  "labels_created": ["needs-info"],
  "labels_removed": [],
  "summary": "..."
}
```

</what-to-do>
