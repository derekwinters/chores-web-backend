# github-issue-validate-bug

Validates bug reports for completeness against 8 strict requirements.

## Usage

```
/github-issue-validate-bug <issue-number>
```

## Strict Requirements

Bug report must contain all 8 fields to be valid:
1. Steps to reproduce (numbered, exact)
2. Expected behavior
3. Actual behavior
4. Environment (OS, version, browser, app version)
5. Error messages/logs
6. Screenshots
7. Frequency (always/sometimes/rarely)
8. Severity/impact assessment

Missing any field → invalid, suggest `needs-info` label.

## Output

```json
{
  "valid": true|false,
  "missing_fields": ["field1", "field2"],
  "target_labels": ["bug", "needs-info"],
  "suggestions": ["suggestion1"],
  "confidence": 0.0-1.0
}
```

## Process

1. Fetch issue via `gh issue view <number>`
2. Check all 8 required fields present
3. Return validation result with missing fields list
4. Suggest labels: `bug` always, plus `needs-info` if invalid
5. Include confidence score

## Integration

- Called by orchestrator (#143)
- Output used by #150 (label applicator)
- Returns target labels for consolidation
