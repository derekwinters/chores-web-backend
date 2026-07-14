---
name: github-issue-plan
description: Lightweight pre-grilling issue review. Use /grill-with-docs issue <N> for the full grilling session that produces the implementation contract.
---

# GitHub Issue Planning (Lightweight)

> **Recommended entry point**: `/grill-with-docs issue <N>` — full grilling session that covers all 4 impact areas, posts structured comment, and flips labels to `ready-for-work`.

This lightweight skill is a quick sanity-check: it reviews issue content and surfaces any obvious gaps before grilling. Use it when you want a fast read-through before committing to a full grilling session.

## Usage

```
/github-issue-plan <issue-number>
```

## Workflow

1. **Fetch issue**: Get complete issue details from GitHub
2. **Check status**: Require `ready-to-grill` label. Warn if missing.
3. **Review requirements**: Summarize issue intent, flag any ambiguities
4. **Surface gaps**: Call out missing context (acceptance criteria, scope boundaries, affected areas)
5. **Recommend grilling**: Suggest running `/grill-with-docs issue <N>` to proceed

## Notes

- Does NOT add labels or post comments — that is the grilling session's job
- Does NOT initiate implementation under any circumstances
- Use `/grill-with-docs issue <N>` to move the issue to `ready-for-work`
