---
name: github-issue-categorize
description: Analyze a GitHub issue to determine its type (bug|feature|refactor|chore) and effort estimate (small|medium|large) with confidence scores. Engine skill called by the triage orchestrator.
---

<what-to-do>

## Invocation

```
/github-issue-categorize <issue-number>
```

Engine skill (not an orchestrator). Returns JSON only.

## Process

1. Fetch issue: `gh issue view <issue-number> --json title,body`
2. Extract title and body content.
3. Categorize **type** based on keywords and context:
   - **bug**: fix, broken, crash, error, issue, regression, problem
   - **feature**: add, implement, new, support, enable, allow
   - **refactor**: refactor, improve, cleanup, optimize, restructure
   - **chore**: update, deps, docs, maintenance, tooling
4. Estimate **effort**:
   - **small**: simple, isolated, <50 lines, <1 hour
   - **medium**: moderate scope, multiple files, 50-200 lines, 1-4 hours
   - **large**: complex, multiple components, >200 lines, >4 hours
5. Provide confidence scores (0.0-1.0) for both type and effort.
6. Return JSON output only.

## Output

```json
{
  "type": "bug|feature|refactor|chore",
  "effort": "small|medium|large",
  "confidence_type": 0.0,
  "confidence_effort": 0.0,
  "reasoning": "brief explanation"
}
```

</what-to-do>
