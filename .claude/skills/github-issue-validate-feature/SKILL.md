---
name: github-issue-validate-feature
description: Validate a feature request against 6 strict completeness requirements, accepting justified N/A responses and flagging unjustified ones. Engine skill called by the triage orchestrator; returns JSON only.
---

<what-to-do>

## Invocation

```
/github-issue-validate-feature <issue-number>
```

Engine skill (not an orchestrator). Returns JSON only.

## Strict Requirements (6 fields)

1. Use case/motivation — why is this needed
2. Description/overview — what is the feature
3. Expected behavior/workflow — how should it work
4. Acceptance criteria — how do we know it's done
5. Edge cases/constraints — corner cases, limits, compatibility
6. Performance/scalability considerations (if applicable)

## N/A validation

- Accept `N/A` only if justified for the feature's scope.
- Flag unjustified N/A as questionable (e.g. "Edge cases: N/A" for a payment feature).
- Justified example: "Performance: N/A" for a simple button.

## Process

1. Fetch issue: `gh issue view <issue-number> --json title,body`.
2. Check all 6 fields present with content.
3. For N/A fields, assess justification based on feature scope.
4. Collect missing fields and questionable N/As.
5. Determine target labels: always include `feature`; add `needs-info` if missing or unjustified-N/A fields exist.
6. Generate suggestions and calculate confidence.
7. Return JSON output only.

## Output

```json
{
  "valid": true,
  "missing_fields": ["field1"],
  "questionable_na_fields": ["field2"],
  "target_labels": ["feature", "needs-info"],
  "suggestions": ["suggestion1"],
  "confidence": 0.0
}
```

</what-to-do>
