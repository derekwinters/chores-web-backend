---
name: github-issue-find-duplicates
description: Search open GitHub issues for duplicates and related work so triage can consolidate. Engine skill called by the triage orchestrator; the user makes the final duplicate decision.
---

<what-to-do>

## Invocation

```
/github-issue-find-duplicates <issue-number>
```

Engine skill (not an orchestrator). Returns JSON only.

## Process

1. Fetch the issue: `gh issue view <issue-number> --json title,body`.
2. Search **open issues only** for related/duplicate work (e.g. `gh issue list --state open --search "<keywords>"`).
3. Score each candidate by relevance (0.0-1.0) and classify as `duplicate`, `related`, or `similar`.
4. Keep only candidates with relevance >= 0.6, return at most the top 10.
5. The user makes the final duplicate decision — this skill only surfaces candidates.

## Output

```json
{
  "related_issues": [
    {"number": 123, "title": "...", "relevance": 0.95, "type": "duplicate|related|similar"}
  ],
  "confidence": 0.85
}
```

</what-to-do>
