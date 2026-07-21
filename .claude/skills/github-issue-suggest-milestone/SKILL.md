---
name: github-issue-suggest-milestone
description: Suggest a milestone for a GitHub issue by matching its type, priority, and complexity against each milestone's focus area. Advisory-only engine skill called by the triage orchestrator; the user decides.
---

<what-to-do>

## Invocation

```
/github-issue-suggest-milestone <issue-number>
```

Engine skill (not an orchestrator). Advisory only — returns a recommendation; the user (or orchestrator policy) makes the final call.

## Process

1. Fetch the issue and its current type/priority/complexity signals.
2. List available milestones: `gh api repos/{owner}/{repo}/milestones` (or `gh milestone list`) and read each milestone's title/description for its focus area.
3. Match the issue's topic to the milestone focus areas, scoring the best topic match (0.0-1.0).
4. Return the suggested milestone plus alternatives and a rationale.

## Output

```json
{
  "suggested_milestone": "v1.2.0",
  "focus_area": "Performance",
  "rationale": "...",
  "topic_match": 0.85,
  "alternatives": ["v1.3.0"],
  "user_decides": true
}
```

</what-to-do>
