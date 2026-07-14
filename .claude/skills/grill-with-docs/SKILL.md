---
name: grill-with-docs
description: Grilling session that challenges your plan against the existing domain model, sharpens terminology, and updates documentation (CONTEXT.md, ADRs) inline as decisions crystallise. Use when user wants to stress-test a plan against their project's language and documented decisions. When invoked as "/grill-with-docs issue <N>", also gates on ready-to-grill label and finalizes by posting a structured comment and flipping labels.
---

<what-to-do>

## Entry Point

If invoked as `/grill-with-docs issue <N>` (with an issue number):

1. **Label gate**: Fetch issue via `gh issue view <N>`. If `ready-to-grill` label is missing, warn the user and ask whether to continue anyway before proceeding.
2. **Load issue context**: Read the issue title, body, and any existing comments to prime the grilling session.
3. Run the full grilling session below.
4. **Finalize**: After the session concludes, post a structured grilling comment to the issue, remove `ready-to-grill`, apply `ready-for-work`.

If invoked without an issue number (generic plan grilling), skip the label gate and finalization steps.

## Grilling Session

Interview me relentlessly about every aspect of this plan until we reach a shared understanding. Walk down each branch of the design tree, resolving dependencies between decisions one-by-one. For each question, provide your recommended answer.

Ask the questions one at a time, waiting for feedback on each question before continuing.

If a question can be answered by exploring the codebase, explore the codebase instead.

## Area Checklist

Every grilling session MUST explicitly cover all five areas. Work through them as part of the conversation, not just in the output:

- [ ] **Backend** — FastAPI routers, endpoints, services, business logic, request/response schemas
- [ ] **Database/Migrations** — `app/models.py` changes and the matching Alembic revision in `alembic/versions/` (see `MIGRATIONS.md`)
- [ ] **API Contract** — changes to the live OpenAPI schema and whether they drift from the golden snapshot in `chores-web-docs` (`docs/api/openapi.json`); breaking changes require the Breaking Change Ritual (bump `API_VERSION`, update the golden snapshot) — see CLAUDE.md
- [ ] **Scheduler** — background jobs and scheduled tasks
- [ ] **Docs** — README, architecture docs, CONTEXT.md, ADRs, any other affected docs

If an area has no changes, state that explicitly ("Scheduler: no changes needed") so it's clear it was considered, not skipped.

</what-to-do>

<supporting-info>

## Domain awareness

During codebase exploration, also look for existing documentation:

### File structure

Most repos have a single context:

```
/
├── CONTEXT.md
├── docs/
│   └── adr/
│       ├── 0001-event-sourced-orders.md
│       └── 0002-postgres-for-write-model.md
└── src/
```

If a `CONTEXT-MAP.md` exists at the root, the repo has multiple contexts. The map points to where each one lives:

```
/
├── CONTEXT-MAP.md
├── docs/
│   └── adr/                          ← system-wide decisions
├── src/
│   ├── ordering/
│   │   ├── CONTEXT.md
│   │   └── docs/adr/                 ← context-specific decisions
│   └── billing/
│       ├── CONTEXT.md
│       └── docs/adr/
```

Create files lazily — only when you have something to write. If no `CONTEXT.md` exists, create one when the first term is resolved. If no `docs/adr/` exists, create it when the first ADR is needed.

## During the session

### Challenge against the glossary

When the user uses a term that conflicts with the existing language in `CONTEXT.md`, call it out immediately. "Your glossary defines 'cancellation' as X, but you seem to mean Y — which is it?"

### Sharpen fuzzy language

When the user uses vague or overloaded terms, propose a precise canonical term. "You're saying 'account' — do you mean the Customer or the User? Those are different things."

### Discuss concrete scenarios

When domain relationships are being discussed, stress-test them with specific scenarios. Invent scenarios that probe edge cases and force the user to be precise about the boundaries between concepts.

### Cross-reference with code

When the user states how something works, check whether the code agrees. If you find a contradiction, surface it: "Your code cancels entire Orders, but you just said partial cancellation is possible — which is right?"

### Update CONTEXT.md inline

When a term is resolved, update `CONTEXT.md` right there. Don't batch these up — capture them as they happen. Use the format in [CONTEXT-FORMAT.md](./CONTEXT-FORMAT.md).

`CONTEXT.md` should be totally devoid of implementation details. Do not treat `CONTEXT.md` as a spec, a scratch pad, or a repository for implementation decisions. It is a glossary and nothing else.

### Offer ADRs sparingly

Only offer to create an ADR when all three are true:

1. **Hard to reverse** — the cost of changing your mind later is meaningful
2. **Surprising without context** — a future reader will wonder "why did they do it this way?"
3. **The result of a real trade-off** — there were genuine alternatives and you picked one for specific reasons

If any of the three is missing, skip the ADR. Use the format in [ADR-FORMAT.md](./ADR-FORMAT.md).

## Finalization (issue grilling only)

After the session is complete and the user confirms the decisions are captured, post this structured comment to the issue and flip labels.

### Comment format

```markdown
## Grilling Session — Issue #N

### Decisions & Clarifications
- [resolved decisions from session]

### Impact Areas
| Area | Changes | Notes |
|------|---------|-------|
| Backend | ... | ... |
| Database/Migrations | ... | ... |
| API Contract | ... | ... |
| Scheduler | ... | ... |
| Docs | ... | ... |

### Behaviors to Implement
- [ ] Behavior 1 (area: Backend)
- [ ] Behavior 2 (area: API Contract)

### CONTEXT.md Updates
- New terms added: ...
- ADRs created: ...
```

### Label flip

```bash
gh issue edit <N> --remove-label "ready-to-grill" --add-label "ready-for-work"
```

</supporting-info>
