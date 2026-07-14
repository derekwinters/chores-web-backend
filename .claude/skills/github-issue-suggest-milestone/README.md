# github-issue-suggest-milestone

Suggests milestone based on issue type, priority, complexity, AND milestone focus areas.

## Output
```json
{
  "suggested_milestone": "v1.2.0",
  "focus_area": "Performance",
  "rationale": "...",
  "topic_match": 0.85,
  "alternatives": [...],
  "user_decides": true
}
```

Advisory only. Matches issue topic to milestone focus areas.
