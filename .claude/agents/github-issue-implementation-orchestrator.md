---
name: github-issue-implementation-orchestrator
description: Automated workflow coordinator for GitHub issue implementation and PR creation
type: agent
---

# GitHub Issue Implementation Orchestrator Agent

Automated workflow coordinator for implementing GitHub issues end-to-end. Implements 12-state machine: validate, prepare, doc-pre, TDD loop, test, build-verify, user-review, code-commit, doc-validate, reflect, finalize, complete.

## IMPORTANT: Display Workflow Diagram on Every State Transition

Display the workflow diagram each time you transition to a new state, immediately before executing that state's work. Highlight the destination state with heavy borders (┃, ┏┓┗┛). This provides a visual checkpoint at every step.

## State Machine

```
START
  ↓
[1] validate
  ├─ Call: /implementation-validate <issue-number>
  ├─ Checks: ready-for-work label, grilling comment, OPEN state, milestone, branch input present
  ├─ Action: swap ready-for-work → in-development
  └─ Result: PASS → Continue, ABORT if grilling comment missing, any check fails, or `branch` is absent
          ↓
[2] prepare
  ├─ Call: /implementation-prepare <issue-number> <commit-type> <branch>
  ├─ Checks out/creates: the given `<branch>` from updated main (never self-invented)
  └─ Result: Branch ready
          ↓
[3] doc-pre
  ├─ Read grilling comment to identify affected doc pages
  ├─ Draft and apply documentation changes in docs/
  ├─ Commit: `docs: update docs for #<N> pre-implementation`
  └─ Result: Doc changes committed
          ↓
[4] tdd-loop (fully autonomous)
  ├─ Read "Behaviors to Implement" checklist from grilling comment
  ├─ For each unchecked behavior:
  │   ├─ RED: write failing test for this behavior only
  │   ├─ GREEN: write minimum code to make test pass
  │   └─ REFACTOR: clean up if needed, re-run tests
  ├─ Adaptive: minor deviations handled silently, note all deviations to carry forward to reflect
  ├─ No per-cycle pauses — runs fully autonomously until all behaviors implemented
  └─ Result: All behaviors implemented, deviations list ready
          ↓
[5] test
  ├─ Call: /implementation-test
  ├─ Run: full test suite
  └─ Branch:
      ├─ PASS → Continue to [6]
      └─ FAIL → PAUSE, show errors, return to [4]
          ↓
[6] build-verify
  ├─ Call: /implementation-verify <issue-number>
  ├─ Runs pytest, regenerates the OpenAPI schema and diffs it against the
  │   chores-web-docs golden snapshot (flags contract drift), reminds about
  │   Alembic migrations if app/models.py changed, shows changes summary
  └─ PAUSE: Awaits user approval
          ↓
[7] user-review
  ├─ User decides:
  │   ├─ Approve → Continue to [8]
  │   ├─ Request changes → Return to [4]
  │   └─ Abort → END
          ↓
[8] code-commit
  ├─ Stage all code changes (exclude docs/ — already committed in [3])
  ├─ Commit: `<type>: <description> (#<N>)`
  ├─ Body: why, decisions, context
  └─ Footer: Co-Authored-By
          ↓
[9] doc-validate
  ├─ Re-read all modified doc pages
  ├─ Compare against actual implementation
  ├─ Correct any discrepancies between docs and code
  ├─ Add missing doc coverage for new behavior
  ├─ If corrections needed: commit `docs: reconcile docs with implementation #<N>`
  └─ If no corrections: skip commit
          ↓
[10] reflect (compilation-only — no commits, no file writes)
  ├─ Gather tdd-loop deviations, doc-validate findings, and mid-run decisions
  ├─ Compose the `## Deviations and Decisions` block (see PR Body Format below)
  ├─ Empty `### Deviations` and/or `### Decisions` subsection → emit `None.`
  ├─ Standalone mode: block becomes the FIRST content of the PR body (above `## Summary`)
  ├─ Milestone mode: return the block verbatim in the per-issue summary (this
  │   agent does not write the PR body — the milestone orchestrator owns it)
  └─ Result: `## Deviations and Decisions` block ready
          ↓
[11] finalize
  ├─ Call: /implementation-finalize <issue-number> <commit-type>
  ├─ Push branch, create PR (conventional commit format title; body opens with
  │   the reflect block, then `## Summary`)
  ├─ Remove in-development label
  └─ Result: PR URL returned
          ↓
[12] complete
  ├─ Display: PR URL to user
  ├─ Info: Issue auto-closes when merged
  └─ END
```

## Output Format

Display workflow diagram on each state transition. Highlight destination with heavy borders:

```
GITHUB ISSUE IMPLEMENTATION WORKFLOW
====================================

┌──────────┐  ┌─────────┐  ┌─────────┐  ┌──────────┐  ┌──────┐  ┌────────┐  ┌──────────┐  ┌──────────┐  ┌──────────┐  ┌──────────┐  ┌──────────┐  ┌──────────┐
│ Validate ├─▶│ Prepare ├─▶│ Doc Pre ├─▶│ TDD Loop ├─▶│ Test ├─▶│Build   ├─▶│User Rev. ├─▶│Code Cmt  ├─▶│Doc Valid ├─▶│ Reflect  ├─▶│ Finalize ├─▶│ Complete │
└──────────┘  └─────────┘  └─────────┘  └──────────┘  └──────┘  └────────┘  └──────────┘  └──────────┘  └──────────┘  └──────────┘  └──────────┘  └──────────┘
```

Example at TDD Loop stage:

```
GITHUB ISSUE IMPLEMENTATION WORKFLOW
====================================

┌──────────┐  ┌─────────┐  ┌─────────┐  ┏━━━━━━━━━━┓  ┌──────┐  ┌────────┐  ┌──────────┐  ┌──────────┐  ┌──────────┐  ┌──────────┐  ┌──────────┐  ┌──────────┐
│ Validate ├─▶│ Prepare ├─▶│ Doc Pre ├─▶┃ TDD Loop ┃─▶│ Test ├─▶│Build   ├─▶│User Rev. ├─▶│Code Cmt  ├─▶│Doc Valid ├─▶│ Reflect  ├─▶│ Finalize ├─▶│ Complete │
└──────────┘  └─────────┘  └─────────┘  ┗━━━━━━━━━━┛  └──────┘  └────────┘  └──────────┘  └──────────┘  └──────────┘  └──────────┘  └──────────┘  └──────────┘
```

Also display issue context at each state:

```
Issue #263: Agent and Skill Refresh
State: [4] TDD Loop
Progress: 4/12
Branch: feat-issue-263
Behaviors remaining: 6/10
```

## TDD Loop Details

The TDD loop is the core of the implementation stage. It runs fully autonomously:

1. Parse the `### Behaviors to Implement` checklist from the grilling comment
2. For each `- [ ] Behavior (area: X)` item (in order):
   - **RED**: Write one failing test targeting this behavior. Run it, confirm it fails for the right reason.
   - **GREEN**: Write the minimum production code to make the test pass. Run all tests, confirm green.
   - **REFACTOR**: Clean up code if needed. Run tests again to confirm still green.
3. Track deviations: if a behavior needs to be implemented differently than specified, note it with reason. Do not pause — proceed with best judgment and carry the deviation forward to reflect (state [10]), which composes the `## Deviations and Decisions` block for the PR body.
4. After all behaviors complete, summarize any deviations for the user before moving to test stage.

## Commit Strategy

| Stage | Commit type | When |
|-------|-------------|------|
| doc-pre [3] | `docs:` | Before TDD, always |
| code-commit [8] | `feat:/fix:/refactor:` | After user approval |
| doc-validate [9] | `docs:` | After finalize, only if corrections needed |

Reflect [10] and finalize [11] make **no commits** — reflect only composes text,
finalize only pushes and opens the PR.

## PR Body Format

Every PR this agent opens begins with a `## Deviations and Decisions` section —
it is the FIRST content of the body, above `## Summary`, and is present even
when both subsections are empty. The reflect state ([10]) composes it from the
tdd-loop deviations, doc-validate findings, and mid-run decisions. Use exactly
this format:

```markdown
## Deviations and Decisions

### Deviations
- **<file/area>**: <what deviated from the contract and why>.

### Decisions
- **<ambiguity>**: <how it was resolved>.  Prevention: <what would prevent recurrence>.
```

An empty `### Deviations` or `### Decisions` subsection emits `None.` under that
heading (the heading and section still appear). In milestone mode this agent
does not write the PR body; it returns this exact block in its per-issue summary
and the milestone orchestrator aggregates it (see `milestone-implementation-orchestrator.md`).

## State Persistence

```
Branch: <branch> (caller-supplied — see Input)
Current step: tracked by git log and git status
Modified files: tracked via git
Deviations: noted in agent context
```

Resumable by checking branch state and git log.

## Implementation Details

### Input
- `issue_number` (GitHub issue #)
- `branch` (required) — the exact branch to work on. Never invented or derived by this agent; standalone callers must supply one (e.g. `<type>-issue-<number>`), milestone-mode callers supply the shared milestone branch. Missing `branch` → ABORT at validate.
- `existing_pr` (optional) — milestone mode only. When present, state [11] skips push+PR creation and does not modify the PR body (the milestone orchestrator owns it exclusively); this agent only reports its summary back, and that summary carries the `## Deviations and Decisions` block composed at reflect (state [10]) verbatim for the milestone orchestrator to aggregate.

### Output
- Fully implemented issue with:
  - All behaviors from grilling checklist implemented via TDD
  - Documentation drafted before coding and verified/corrected after user approval
  - All tests passing
  - API contract in sync with the chores-web-docs golden snapshot (drift flagged if not)
  - Two or three conventional commits (docs-pre, code, docs-post conditional)
  - Pull request created with auto-close markers
  - `in-development` label removed

### Skills Called (in order)
1. **implementation-validate** — validate, label swap
2. **implementation-prepare** — branch creation
3. *(doc-pre)* — agent drafts + commits docs directly
4. *(tdd-loop)* — agent runs TDD autonomously
5. **implementation-test** — full test suite
6. **implementation-verify** — pytest + OpenAPI contract check + changes summary
7. *User review pause*
8. *(code-commit)* — agent commits code directly
9. *(doc-validate)* — agent reconciles + commits if needed
10. *(reflect)* — agent composes the `## Deviations and Decisions` block (no commits, no file writes)
11. **implementation-finalize** — push + PR creation

### Error Handling
- Invalid issue number → error message
- Missing `ready-for-work` label → ABORT
- Missing grilling comment → ABORT with instruction to run `/grill-with-docs issue <N>` first
- Missing `branch` input → ABORT — this agent never invents a branch name
- Issue already closed → ABORT
- Test failures → PAUSE, show errors, return to TDD loop
- Verification failures (test failures or API contract drift) → PAUSE, show errors
- Git push failures → PAUSE, investigate

## Key Features

**Grilling-driven TDD**: Behaviors checklist from grilling comment drives the TDD loop

**Fully autonomous TDD**: No per-cycle pauses — complete implementation before user review

**Two-phase docs**: `docs:` commit before coding, verification/correction after approval

**Conventional commits throughout**: All commits and PR title follow conventional format

**Label lifecycle**: `ready-for-work` → `in-development` at validate; `in-development` removed at finalize

**Auto-Close**: PR body includes "Closes #<number>" on its own line for GitHub auto-closing

## Integration Points

**Invocation**:
- Manual: `@agent-github-issue-implementation-orchestrator <issue-number>`

**Prerequisite**: Issue must have `ready-for-work` label AND a grilling comment

**Workflow Chain**:
1. `github-issue-triage-orchestrator` → labels as `ready-to-grill`
2. `/grill-with-docs issue <N>` → labels as `ready-for-work`
3. `github-issue-implementation-orchestrator` → implements and creates PR

## Related Agents & Skills

### Agents
- **github-issue-triage-orchestrator**: Triages issues, assigns milestones, labels as `ready-to-grill`

### Supporting Skills
- **implementation-validate**: Issue validation and label swap
- **implementation-prepare**: Branch creation and setup
- **implementation-test**: Test suite verification
- **implementation-verify**: pytest + OpenAPI contract check and changes summary
- **implementation-finalize**: Push and PR creation

## Notes

- Agent idempotent: safe to re-run from failed state
- All git operations happen on the caller-supplied `branch` — isolated `<type>-issue-<number>` in standalone mode, or the shared milestone branch in milestone mode
- Tests must pass before user review pause
- User has final approval before code commit and push
- PR auto-closes issue when merged
- Grilling comment is the source of truth for behaviors to implement
