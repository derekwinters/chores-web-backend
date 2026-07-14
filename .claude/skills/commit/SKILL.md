---
name: commit
description: Run tests and create conventional commit with proper type and scope
---

# Commit Skill

Validates all tests pass, then creates a Conventional Commit with proper type/scope.

## Usage

```
/commit
```

## Flow

1. Run the test suite (`pytest`)
2. Stop if any tests fail — report failures
3. Review staged/unstaged changes
4. Derive commit type and scope from changes
5. Create commit using Conventional Commits format

## Commit Format

```
<type>(<scope>): <short description>

[optional body explaining why]
```

## Types

- `feat` - new feature
- `fix` - bug fix
- `refactor` - code restructuring
- `test` - test additions/changes
- `docs` - documentation
- `chore` - build/deps/tooling
- `style` - formatting
- `perf` - performance
- `ci` - CI/CD changes

## Scopes

- `api` - routers, endpoints, request/response schemas
- `db` - models, migrations, persistence layer
- `auth` - authentication, token handling, auth log
- `scheduler` - background jobs, scheduled tasks
- `services` - business logic, service layer
- `build` - dependencies, packaging, tooling config
- Use most relevant scope

## Rules

- Subject line ≤72 characters, lowercase, no period
- Imperative mood: "add" not "added"
- Body only when "why" is non-obvious
- Stage changes before invoking
