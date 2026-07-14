# github-issue-validate-refactor

Validates refactor requests with 3 core requirements. Lighter than feature validation (internal work).

## Usage

```
/github-issue-validate-refactor <issue-number>
```

## Core Requirements (3 fields)

1. Scope - what's changing (files, modules, components)
2. Rationale - efficiency gains expected, why refactor now
3. Risk assessment - what could break, regressions to watch

N/A rarely acceptable (internal work assumes context).

## Output

```json
{
  "valid": true|false,
  "missing_fields": ["field1"],
  "target_labels": ["refactor", "needs-info"],
  "suggestions": ["suggestion1"],
  "confidence": 0.0-1.0
}
```

## Integration

- Called by orchestrator (#143)
- Output used by #150 (label applicator)
- Lighter validation (internal work, assumes submitter context)
