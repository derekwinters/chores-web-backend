---
name: github-issue-validate-refactor
description: Validate a refactor request against 3 core requirements (lighter than feature validation, since it is internal work). Engine skill called by the triage orchestrator; returns JSON only.
---

<what-to-do>

## Invocation

```
/github-issue-validate-refactor <issue-number>
```

Engine skill (not an orchestrator). Returns JSON only.

## Core Requirements (3 fields)

1. Scope — what's changing (files, modules, components)
2. Rationale — efficiency gains expected, why refactor now
3. Risk assessment — what could break, regressions to watch

N/A is rarely acceptable (internal work assumes submitter context).

## Process

1. Fetch issue: `gh issue view <issue-number> --json title,body`.
2. Check the 3 fields are present.
3. Determine target labels: always include `refactor`; add `needs-info` if invalid.
4. Return JSON with valid status, missing fields, target labels, suggestions, and confidence.

## Output

```json
{
  "valid": true,
  "missing_fields": ["field1"],
  "target_labels": ["refactor", "needs-info"],
  "suggestions": ["suggestion1"],
  "confidence": 0.0
}
```

</what-to-do>
