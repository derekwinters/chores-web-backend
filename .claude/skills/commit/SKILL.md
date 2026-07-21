---
name: commit
description: Run the repo's tests, then create a Conventional Commit with proper type and scope.
---

# Commit Skill

Validates the suite passes, then creates a Conventional Commit with the right
type/scope. Stage changes before invoking.

## Usage

```
/commit
```

## Flow

1. Run the test suite: `pytest`
2. Stop if anything fails — report failures; do NOT commit.
3. Review staged/unstaged changes (`git diff --staged`, `git status`).
4. Derive commit type and scope from the actual changes.
5. Create the commit in Conventional Commits format.

## Format

```
<type>(<scope>): <short description>

[optional body explaining why]
```

## Types

`feat` (feature) · `fix` (bug) · `refactor` · `test` · `docs` · `chore`
(build/deps/tooling) · `style` · `perf` · `ci`. Pick by the actual semver impact
of the change, not by what a PR title happens to say.

## Scopes

Use the most relevant of: `api, db, auth, scheduler, services, build`.



## Rules

- Subject ≤72 chars, lowercase, no trailing period, imperative mood ("add" not "added").
- Body only when the "why" is non-obvious.
- This skill never invents a branch or pushes — it only commits.
