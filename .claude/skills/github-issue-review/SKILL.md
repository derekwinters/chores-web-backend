---
name: github-issue-review
description: Review GitHub issue content for completeness, clarify missing sections in place, and apply the ready-to-grill label when the issue is complete.
---

<what-to-do>

## Invocation

```
/github-issue-review <issue-number>
```

Reviews a GitHub issue for completeness, updates its description/acceptance criteria as needed, and labels it `ready-to-grill` when complete.

## Step 1: Fetch and check status

- Fetch the issue: `gh issue view <number>`.
- Extract its labels.
- If the issue already has `ready-to-grill` OR `ready-for-work`, STOP and inform the user: "Issue already labeled, skipping review."
- Otherwise continue.

## Step 2: Review completeness

Assess whether the issue has these elements:

- **Title** — clear and specific (not vague like "Bug" or "Fix something").
- **Description** — explains the problem/feature, at least 2-3 sentences of context, covering the "what" and the "why".
- **Acceptance criteria** — specific requirements or a definition of done; at least 3 criteria (or equivalent detail), each testable/verifiable.
- **Context/examples** (helpful but not strictly required) — environment details, reproduction steps or code examples, related issues.

## Step 3: Identify gaps

Determine what is missing: unclear title, insufficient description, no/weak acceptance criteria, vague requirements, missing examples or context.

## Step 4: Update the issue (if needed)

If gaps are found, update the issue body: `gh issue edit <number> --body "<new-body>"`.

- Add an `## Acceptance Criteria` section if missing.
- Clarify vague requirements; add examples or test cases.
- Link related issues; add implementation hints if helpful.
- Keep the original content — only add or clarify missing sections, never remove information.

## Step 5: Add label

- Apply the label: `gh issue edit <number> --add-label ready-to-grill`.
- Confirm the label was added.

## Step 6: Summary

Report the issue number and title, what was reviewed/updated, and confirmation that the `ready-to-grill` label was added.

## Rules

- Do NOT modify the issue if `ready-to-grill` or `ready-for-work` is already present.
- Preserve the submitter's original intent and language; be respectful.
- Only add or clarify — do not remove information.
- Focus on completeness, not style. Some issues need no updates (already complete). Be conservative with changes; ask before major rewrites.

## Labels

- **ready-to-grill** — issue is complete and ready for the grilling / planning stage (applied by this skill).
- **ready-for-work** — issue already planned; skip this workflow.

</what-to-do>
