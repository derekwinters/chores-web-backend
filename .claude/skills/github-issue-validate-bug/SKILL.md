---
name: github-issue-validate-bug
description: Validate a bug report against 8 strict completeness requirements and suggest labels. Engine skill called by the triage orchestrator; returns JSON only.
---

<what-to-do>

## Invocation

```
/github-issue-validate-bug <issue-number>
```

Engine skill (not an orchestrator). Returns JSON only.

## Strict Requirements (all 8 must be present with substantive content)

1. Steps to reproduce (numbered, exact steps)
2. Expected behavior (what should happen)
3. Actual behavior (what actually happens)
4. Environment (OS, version, browser, app version)
5. Error messages/logs (stack traces, error details)
6. Screenshots (visual evidence)
7. Frequency (always/sometimes/rarely)
8. Severity/impact assessment (critical/high/medium/low)

Missing any field → invalid.

## Process

1. Fetch issue: `gh issue view <issue-number> --json title,body`.
2. Check all 8 fields are present with substantive content.
3. Collect the missing fields list.
4. Determine target labels: always include `bug`; add `needs-info` if any fields are missing.
5. Generate suggestions for the missing fields.
6. Calculate confidence (1.0 if valid, lower if ambiguous).
7. Return JSON output only.

## Output

```json
{
  "valid": true,
  "missing_fields": ["field1", "field2"],
  "target_labels": ["bug", "needs-info"],
  "suggestions": ["suggestion1"],
  "confidence": 0.0
}
```

</what-to-do>
