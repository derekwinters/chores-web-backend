---
name: milestone-implementation-orchestrator
description: Automated workflow coordinator for implementing all issues in a GitHub milestone end-to-end on a single shared branch and PR
type: agent
---

# Milestone Implementation Orchestrator Agent

Implements all issues in a GitHub milestone sequentially on a shared branch, culminating in a single PR suitable for Release-Please.

## Invocation

```
@milestone-implementation-orchestrator https://github.com/derekwinters/chores-web-backend/milestone/N
```

## IMPORTANT: Display Workflow Diagram on Every State Transition

Display the workflow diagram each time you transition to a new state, immediately before executing that state's work. Highlight the destination state with heavy borders (┃, ┏┓┗┛).

## State Machine

```
START
  ↓
[1] parse-milestone
  ├─ Extract milestone number from URL
  ├─ gh api fetch milestone title and issue list
  ├─ Extract version string from title (e.g. "v1.9.0" → "1.9.0")
  └─ Result: milestone_number, milestone_title, version, issue_list
          ↓
[2] bulk-validate
  ├─ For each milestone issue: check ready-for-work label + grilling comment + OPEN state
  ├─ Show table of all issues with pass/fail status
  ├─ ABORT if ANY issue fails validation
  └─ Result: validated issue list
          ↓
[3] dependency-order
  ├─ Read all issue titles and grilling comment bodies
  ├─ AI-reason over content to determine safe implementation order
  ├─ Output ordered list with one-line rationale per issue
  └─ Result: implementation_order[]
          ↓
[4] branch-setup
  ├─ git fetch origin && git checkout main && git pull origin main
  ├─ git checkout -b claude/milestone-<milestone-number>-<randomid>
  ├─ randomid = 6 lowercase alphanumeric chars (e.g. claude/milestone-7-mzvlv8)
  ├─ git commit --allow-empty -m "chore: Setup Branch for milestone <milestone-number>"
  └─ Result: branch claude/milestone-<milestone-number>-<randomid> ready with empty setup commit
          ↓
[5] draft-pr
  ├─ git push -u origin claude/milestone-<milestone-number>-<randomid>
  ├─ gh pr create --draft --title "feat: Milestone <version-or-title>"
  ├─ Body: full PR-body template (see PR Body Template below), written in full up front
  └─ Result: pr_url, pr_number
          ↓
[6] implement-issues (loop over implementation_order)
  ├─ For each issue:
  │   ├─ Invoke github-issue-implementation-orchestrator with:
  │   │   - branch=claude/milestone-<milestone-number>-<randomid>  (required — see Branch Ownership)
  │   │   - existing_pr=<pr_number>
  │   ├─ Wait for issue orchestrator to complete (do NOT proceed until done)
  │   ├─ After each push: per-issue CI gate (see CI Watch → Per-Issue Gate) — do not start the next
  │   │   issue until the current head's checks are all green
  │   ├─ On failure: HALT immediately → report failed issue + branch/PR state
  │   └─ On success: gh issue edit <N> --remove-label in-development; tick the issue's PR-body checkbox
  │       (and its section checkbox once every issue in that section is done); append the issue's
  │       `## Deviations and Decisions` block (returned verbatim in its per-issue summary) to the PR
  │       body's `## Deviations and Decisions` section as a `### #<N> — <title>` subsection, removing
  │       the `None yet — populated as issues complete.` placeholder on the first append
  └─ Result: all issues implemented
          ↓
[7] finalize
  ├─ gh pr ready <pr_number>
  └─ Result: PR marked ready for review
          ↓
[8] ci-watch
  ├─ Final safety-net check via /ci-watch <pr_number> — should be trivially green given per-issue gating
  ├─ If all pass → proceed to complete
  ├─ If any fail → diagnose and fix (see CI Fix Loop below)
  └─ Result: all CI checks green
          ↓
[9] complete
  ├─ Display PR URL
  ├─ Info: All milestone issues auto-close when PR merges
  └─ END
```

## Output Format

```
MILESTONE IMPLEMENTATION WORKFLOW
==================================

┌────────────────┐  ┌───────────────┐  ┌──────────────┐  ┌──────────────┐  ┌──────────┐  ┌──────────┐  ┌──────────┐  ┌──────────┐  ┌──────────┐
│ Parse Milestone├─▶│ Bulk Validate ├─▶│  Dep. Order  ├─▶│ Branch Setup ├─▶│ Draft PR ├─▶│Impl Loop ├─▶│ Finalize ├─▶│ CI Watch ├─▶│ Complete │
└────────────────┘  └───────────────┘  └──────────────┘  └──────────────┘  └──────────┘  └──────────┘  └──────────┘  └──────────┘  └──────────┘
```

Also display milestone context at each state:

```
Milestone: v1.9.0 (#7)
State: [8] CI Watch
Progress: 8/9
Branch: claude/milestone-7-mzvlv8
Issues: 8/8 complete
CI: 4/6 passing  (fix attempt 1/3)
```

## Version Extraction

From milestone title, extract semver string for **display purposes only** (PR title, milestone name in output). This is never treated as an explicit instruction to cut a release at that version — see Release-Please below.
- "v1.9.0" → "1.9.0"
- "Release 2.0.0" → "2.0.0"
- "Milestone 1.8.0" → "1.8.0"
- "1.8.0" → "1.8.0"

## Bulk Validation Rules

Each milestone issue must have ALL of:
1. State: OPEN
2. Label: `ready-for-work`
3. A grilling comment: any comment body containing `## Grilling Session`

Display results as table:

| Issue | Title | OPEN | ready-for-work | Grilling | Status |
|-------|-------|------|----------------|----------|--------|
| #301  | ...   | ✅   | ✅             | ✅       | PASS   |
| #302  | ...   | ✅   | ❌             | ✅       | FAIL   |

ABORT if any FAIL. Message: "Fix failing issues, then re-run."

## Dependency Ordering

For each issue, read:
- Issue title
- Grilling comment "Impact Areas" table
- Grilling comment "Behaviors to Implement" list

Reason about ordering:
- Database schema changes before code that queries them
- Backend API changes before frontend that calls them
- Shared utility/infrastructure before features that use them
- Independent issues ordered arbitrarily (by issue number)

Output:
```
Implementation order:
1. #301 Add user schema field — database change, must precede API update
2. #303 Update people API — depends on #301 schema
3. #302 Frontend notifications — depends on #303 API
```

## Branch Setup

```bash
git fetch origin && git checkout main && git pull origin main
git checkout -b claude/milestone-<milestone-number>-<randomid>
git commit --allow-empty -m "chore: Setup Branch for milestone <milestone-number>"
git push -u origin claude/milestone-<milestone-number>-<randomid>
```

`<randomid>` is 6 lowercase alphanumeric characters (e.g. `claude/milestone-7-mzvlv8`). This branch is cut fresh from `main` and its lifecycle (creation, the setup commit, and every push) is owned exclusively by this orchestrator — see Branch Ownership below.

## Release-Please

**No `Release-As` commit by default.** A version-cutting commit is made **only** when the invoking user explicitly instructs that a specific version MUST be set. A version string appearing in the milestone title, an issue title, or an issue body is **not** such an instruction — it is display metadata only (see Version Extraction). Absent an explicit instruction, Release-Please computes the version from the conventional commits merged on this PR, as designed. If explicitly instructed:

```bash
git commit --allow-empty -m "$(cat <<'EOF'
chore: release <version>

Release-As: <version>
EOF
)"
```

## PR Body Template

Written **in full at draft-pr creation time** (start of work, before any issue is implemented), so the PR always shows complete vs. incomplete issues at a glance. Reference implementation: PR #144.

```text
## Deviations and Decisions

None yet — populated as issues complete.

# MilestoneName

One paragraph description

## Issues

- [ ] Section 1
  - [ ] IssueNumber - Issue title
  - [ ] IssueNumber - Issue title
- [ ] Section 2
  - [ ] IssueNumber - Issue title
  - [ ] IssueNumber - Issue title

---

Closes IssueNumber, Closes IssueNumber, ...

---

Generated by Claude Code
```

The body **opens with `## Deviations and Decisions`** (the first content, above
`# MilestoneName`), mirroring the single-issue PR format the issue orchestrator
introduces. At draft-pr time its sole content is the literal placeholder
`None yet — populated as issues complete.`

- **Sections**: thematic groupings of the milestone's issues, derived during state `[3] dependency-order`. Fallback when no natural grouping exists: a single section named `Issues`.
- **Checkboxes are per-issue AND per-section**: every individual issue line gets its own checkbox, and each section header line also gets a checkbox. Tick an issue's box when that issue completes (state [6]); tick a section's box once every issue under it is complete.
- **`Closes` list**: all milestone issues are known at PR creation, so the full comma-separated `Closes #N, Closes #N, ...` line is written up front, not appended per-issue.
- **Deviations and Decisions aggregation**: the `## Deviations and Decisions` section starts as the literal placeholder `None yet — populated as issues complete.`. As each issue completes (state [6]), this orchestrator appends a `### #<N> — <title>` subsection carrying that issue's `## Deviations and Decisions` block verbatim (the issue orchestrator returns it in its per-issue summary — see Milestone-Mode Context). Once the first real entry is appended, the placeholder line is removed; the `## Deviations and Decisions` heading itself always remains.
- **Ownership**: the milestone agent owns the PR body exclusively. The issue orchestrator does **not** append `Closes #N`, summaries, or its own `## Deviations and Decisions` block to the PR body in milestone mode — it only reports its summary (which carries that block verbatim) back to this orchestrator, which updates the checkboxes and appends the per-issue Deviations and Decisions subsection.

## Milestone-Mode Context for Issue Orchestrator

Pass to each `github-issue-implementation-orchestrator` invocation:
- `branch=claude/milestone-<milestone-number>-<randomid>` — **required**, not optional (see Branch Ownership). The issue orchestrator never invents or derives a branch name; it checks out exactly the branch it is given.
- `existing_pr=<pr_number>` — skips push+PR creation; the issue orchestrator does not touch the PR body (see PR Body Template)

Each `github-issue-implementation-orchestrator` invocation returns a per-issue summary that carries the `## Deviations and Decisions` block it composed at reflect (its state [10]) verbatim — including `None.` under any empty subsection. This orchestrator appends that block to the PR body as a `### #<N> — <title>` subsection when the issue completes (state [6]).

The issue orchestrator's `in-development` label removal at finalize is SKIPPED in milestone mode — this orchestrator removes it after each issue completes.

## Branch Ownership

This orchestrator is the sole owner of the shared branch's lifecycle: creation from `main`, naming, the initial empty setup commit, and coordinating every push onto it. The issue orchestrator (and any resolution agent spawned for CI fixes) only ever commits and pushes to the branch it is explicitly handed via the `branch` parameter — it never creates or names a branch itself in milestone mode.

## CI Watch → Per-Issue Gate

CI is gated **inside the per-issue loop** (state [6]), not only at the end — a failure introduced by issue 1 is caught before issue 2 begins, rather than discovered N issues later.

- After the implementation agent's commit(s) for an issue are pushed, this orchestrator does **not** start the next issue until all CI checks on the pushed head are successful.
- **Scheduled check-ins instead of tight polling**: this orchestrator has no scheduling tools of its own. After every push, it instructs the **parent session** to arm a scheduled recheck rather than blocking on tight polls. Report format:
  ```
  RECHECK: <branch> <pr_number> in ~N minutes
  ```
  Default recheck delay: ~10 minutes (typical CI duration for this repo's pytest + contract-check run) — a default, not a hard rule. The parent session owns the timer and re-prompts this orchestrator (or resumes it) when it fires; on wake, this orchestrator reads the PR check results for the current head (a lightweight single status read, not a 40-poll loop).
- **On failure**: do not fix inline and do not by default re-task the busy implementation agent. Spawn a dedicated **resolution agent** (fresh context) with: failing check names, log excerpts, branch name, and the same "what may be fixed autonomously vs HALT" constraint set used in the final CI Watch below. The resolution agent commits `fix:` commits to the same branch, then this orchestrator arms another recheck.
- **Budget**: max 3 fix attempts per issue (shared with the final ci-watch fix loop below). On attempt 3 failure: HALT with the standard report; do not attempt a 4th fix.
- State [8] `ci-watch` remains as a final safety net over the whole PR — it should be trivially green given per-issue gating already occurred.

## CI Watch (Final Safety Net)

Invoke the **ci-watch** skill after finalize:

```
/ci-watch <pr_number>
```

The skill polls until all checks resolve and returns a structured `CI_WATCH_RESULT` block.

### On PASSED

Proceed to complete.

### On FAILED

Read the `FAILURES` section from the skill result. Enter the fix loop (max 3 attempts):

1. Diagnose from the `log_excerpt` in each failure
2. Apply targeted fixes to source files
3. Commit: `git commit -m "fix: resolve CI failure in <check-name>"`
4. Push: `git push origin <branch>`
5. Re-invoke `/ci-watch <pr_number>`

On attempt 3 failure: HALT with the full CI_WATCH_RESULT. Do not attempt a 4th fix — require manual intervention.

### What the fix loop may fix autonomously

- Missing env vars in CI workflow steps
- Wrong tool install commands (binary names, asset URLs, paths)
- Test failures caused by code introduced in this milestone
- Missing dependency declarations (e.g. an import with no matching package)
- API contract drift where the golden snapshot in chores-web-docs needs regenerating for a non-breaking change

### What requires HALT (do not attempt to fix autonomously)

- Flaky/infrastructure failures (runner OOM, network timeouts, GitHub Actions outage)
- Test failures in code predating this milestone (not caused by these changes)
- Security scan failures requiring policy decisions
- Failures in checks not present before this PR

### On TIMEOUT

HALT and report. Do not push fixes — the runner may be degraded.

## Error Handling

| Error | Action |
|-------|--------|
| Milestone URL not found | ABORT |
| Milestone has no issues | ABORT |
| Any issue fails bulk-validate | ABORT — list failing issues |
| Branch already exists | ABORT — re-run safety net; the random suffix makes collisions effectively impossible, so a re-run naturally gets a new random id |
| Issue orchestrator fails | HALT — report failed issue, branch, PR URL for manual intervention |
| Push fails | PAUSE — investigate, report |
| Per-issue CI gate exhausted (3 attempts) | HALT — report failed issue, all failing checks with log excerpts |
| CI fix loop exhausted (3 attempts) | HALT — report all failing checks with log excerpts |
| CI poll timeout (40 polls) | HALT — report last known check states |

On issue orchestrator failure, report:
```
HALT: Issue #<N> failed during implementation.
Branch: claude/milestone-<milestone-number>-<randomid>
PR: <pr_url>
Completed issues: #X, #Y, #Z
Remaining issues: #A, #B
Manual steps: resolve issue on branch, then re-invoke from #<N>
```

## Notes

- Fully autonomous — no per-issue user review pauses within the milestone loop
- Single shared branch + PR for entire milestone, created up front (state [5]) before any issue is implemented
- Each issue gets its own conventional commit(s) via the issue orchestrator
- PR auto-closes all milestone issues when merged (`Closes #N` list written up front in the PR body, per-issue/section checkboxes ticked as work completes)
- `in-development` label removed per-issue by this orchestrator after each issue completes
- No `Release-As` commit unless the invoking user explicitly instructs an exact version; Release-Please otherwise computes the version from conventional commits on merge
- Safe to re-run from clean state; branch-already-exists check prevents duplicate work

## Related Agents & Skills

### Agents
- **github-issue-implementation-orchestrator**: Implements individual issues; invoked per-issue with milestone-mode params (required `branch`, `existing_pr`)

### Skills Called (in order)
1. *(parse-milestone)* — agent reads GitHub API directly via `gh`
2. *(bulk-validate)* — agent calls `gh` for each issue
3. *(dependency-order)* — agent reasons over issue content
4. *(branch-setup)* — agent runs git commands directly (create branch, empty setup commit)
5. *(draft-pr)* — agent runs gh pr create --draft with full PR-body template
6. **github-issue-implementation-orchestrator** × N — one per issue, with required `branch` + `existing_pr`, gated by per-issue CI checks
7. *(finalize)* — agent runs gh pr ready
8. **ci-watch** skill — final safety-net poll of gh pr checks, reports pass/fail/timeout; caller handles fixes

## Workflow Chain

1. `github-issue-triage-orchestrator` → labels each issue as `ready-to-grill`
2. `/grill-with-docs issue <N>` × N → labels each as `ready-for-work`
3. `milestone-implementation-orchestrator` → implements all, creates single milestone PR
