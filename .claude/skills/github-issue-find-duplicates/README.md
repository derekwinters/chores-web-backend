# github-issue-find-duplicates

Searches for related and duplicate issues to help consolidate work.

## Output
```json
{
  "related_issues": [
    {"number": 123, "title": "...", "relevance": 0.95, "type": "duplicate|related|similar"}
  ],
  "confidence": 0.85
}
```

## Parameters
- Relevance threshold: >= 0.6
- Max results: Top 10 issues
- Search scope: Open issues only
- User makes final duplicate decision
