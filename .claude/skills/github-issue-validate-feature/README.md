# github-issue-validate-feature

Validates feature requests for completeness with strict requirements. Accepts justified N/A responses.

## Usage

```
/github-issue-validate-feature <issue-number>
```

## Strict Requirements (6 fields)

1. Use case/motivation - why is this needed
2. Description/overview - what is the feature
3. Expected behavior/workflow - how should it work
4. Acceptance criteria - how do we know it's done
5. Edge cases/constraints - corner cases, limits, compatibility
6. Performance/scalability considerations

N/A is acceptable if justified. Unjustified N/A flagged as questionable.

## Output

```json
{
  "valid": true|false,
  "missing_fields": ["field1"],
  "questionable_na_fields": ["field2"],
  "target_labels": ["feature", "needs-info"],
  "suggestions": ["suggestion1"],
  "confidence": 0.0-1.0
}
```

## Integration

- Called by orchestrator (#143)
- Output used by #150 (label applicator)
- Stricter than bug validation to ensure feature quality
