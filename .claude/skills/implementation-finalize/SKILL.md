---
name: implementation-finalize
description: Push the branch and open the PR (conventional title). Does NOT commit. Removes in-development.
---

# Implementation Finalize Skill

Pushes the branch to origin and creates the pull request. Commits are made at
earlier stages; this skill handles push + PR creation only.

## Usage

```
/implementation-finalize <issue-number> <commit-type>
```

## Workflow

1. **Push branch:** `git push -u origin <branch-name>`.
2. **Create PR:**
   - Title: conventional commit format — `<type>: <description> (#<number>)`.
   - Body: opens with `## Deviations and Decisions` (composed at the
     orchestrator's reflect state; `None.` under any empty subsection), then
     `## Summary`, then `## Implementation`, then a bare `Closes #<number>` on
     its own line (so GitHub auto-closes).
3. **Remove `in-development` label.**
4. **Return the PR URL.**

## PR body template

```
## Deviations and Decisions

### Deviations
- **<file/area>**: <what deviated from the contract and why>.

### Decisions
- **<ambiguity>**: <how it was resolved>. Prevention: <what would prevent recurrence>.

## Summary
- <bullets summarizing changes>

## Implementation
- <what changed>
- Tests: <what was tested>

Closes #<issue-number>
```

## Milestone Mode

When invoked with `existing_pr` (milestone mode), push to the existing shared
branch and do **not** create or modify a PR — the milestone orchestrator owns
the PR body. Return a short summary (issue number, title, commit subject) for
the orchestrator to tick that issue's checkbox. In milestone mode the
orchestrator removes `in-development` after each issue completes.

## Notes

- Does NOT stage or commit — commits happen at the doc-pre, post-approval, and
  doc-validate stages of the orchestrator.
- The squash-merge title is what release-please parses, so it must itself be a
  valid Conventional Commit.
