# github-issue-categorize

Analyzes GitHub issue content to determine type (bug|feature|refactor|chore) and effort estimate.

## Usage

```
/github-issue-categorize <issue-number>
```

## Input

- Issue number (GitHub issue #)

## Output

```json
{
  "type": "bug|feature|refactor|chore",
  "effort": "small|medium|large",
  "confidence_type": 0.0-1.0,
  "confidence_effort": 0.0-1.0,
  "reasoning": "brief explanation"
}
```

## Categorization Rules

**Type:**
- **bug**: Fix, broken, crash, error, issue, regression, problem
- **feature**: Add, implement, new, support, enable, allow
- **refactor**: Refactor, improve, cleanup, optimize, restructure
- **chore**: Update, deps, docs, maintenance, tooling

**Effort:**
- **small**: Simple, isolated change, <50 lines, <1 hour
- **medium**: Moderate scope, multiple files, 50-200 lines, 1-4 hours
- **large**: Complex, multiple components, >200 lines, >4 hours

## Process

1. Fetch issue via `gh issue view <number>`
2. Analyze title + body
3. Determine type based on keywords and context
4. Estimate effort based on scope/complexity
5. Return JSON with type, effort, confidence scores

## Integration

- Called by orchestrator (#143)
- Output used by #150 (label applicator)
