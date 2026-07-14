# github-issue-label

Applies labels to GitHub issues. Label application engine (not orchestrator).

## Input
```json
{
  "issue_number": 123,
  "labels_to_apply": ["bug", "needs-info"],
  "labels_to_remove": [],
  "labels_to_keep": []
}
```

## Output
```json
{
  "labels_applied": [...],
  "labels_created": [...],
  "labels_removed": [],
  "summary": "..."
}
```

Idempotent. Receives data from orchestrator.
