# CLAUDE.md — Developer and AI Agent Reference

This repo is the FastAPI backend for chores-web. The frontend lives in
`derekwinters/chores-web-frontend`; user-facing docs and the **API contract**
live in `derekwinters/chores-web-docs`.

## API Versioning Rules

All API routes are versioned under `/api/v1/`. The status endpoints
(`/status/`) are unversioned infrastructure and must not be prefixed.

The API contract is owned by the `chores-web-docs` repo (contract-first):
the golden OpenAPI snapshot lives at `docs/api/openapi.json` there, next to
the `API_VERSION` file. This backend must conform to that contract — CI
checks out `chores-web-docs` and runs `oasdiff` against the live schema on
every PR.

### Breaking Change Ritual (cross-repo)

CI hard-fails when `oasdiff` detects a breaking change against the published
contract. To introduce a breaking change:

1. Open a PR to `chores-web-docs` that increments `API_VERSION`
   (e.g., `1` → `2`) and updates `docs/api/openapi.json` with the new
   contract (generate it here: `python scripts/generate_openapi.py --output
   <path-to-docs-clone>/docs/api/openapi.json`).
2. In this repo, mount new routes under `/api/v{N}/` alongside existing ones.
3. Merge the docs PR first (or together) — the contract check here diffs
   against `chores-web-docs@main`.

An AI given "add a required parameter and update tests" will not
automatically do any of these steps — that is the enforcement guarantee.

### What counts as a breaking change?
- Removing an endpoint or HTTP method
- Adding a required request parameter or body field
- Changing a field type in a response
- Renaming a path parameter
- Removing a response field that clients may depend on

### What does NOT count as a breaking change?
- Adding an optional request parameter
- Adding a new endpoint
- Adding a new optional response field
- Changing error messages (but not error codes)

## Password Reset Flow

When a user has `requires_password_reset = True`, `POST /v1/auth/login`
returns HTTP 403 with body:
```json
{"reset_token": "<short-lived JWT>", "detail": "Password change required"}
```
The client uses this token to call `PUT /v1/auth/password/reset` with the
new password. On success the endpoint returns a normal LoginResponse.

## Auth Log

All authentication events are stored in `auth_log` (not `user_log`):
- `login_succeeded` / `login_failed`
- `password_changed` (self-service and admin)
- `password_reset`
- `user_created`

Available at `GET /v1/auth/log` (admin only).

## Releases

Versioning is automated with release-please (config under
`.github/release-please/`), which parses commit messages on `main` to
compute version bumps and changelog entries. Releases publish
`ghcr.io/derekwinters/chores-web-backend`.

### Conventional Commits are mandatory

Every commit that lands on `main` MUST be Conventional Commits format —
this is a hard requirement, not a style preference. This applies above all
to squash-merge titles, since the squash title becomes the one commit
release-please ever sees for that PR.

Format: `type(scope): description`, where `type` is one of `feat`, `fix`,
`chore`, `ci`, `docs`, `build`, `refactor`, `test`, `perf`, `revert`.

Pick `type` based on the actual semver impact of the change, not on
whatever the PR title happens to say:
- A new public API endpoint is `feat`, even if the same PR also fixes a
  bug along the way.
- Never default to a missing or vague type, and never copy a PR title
  into the squash-merge title verbatim unless that title is already
  conventional. A non-conventional title that slips through is silently
  invisible to release-please — it will not appear in the changelog and
  will not trigger the version bump it should.

Before merging, either fix the PR title/squash message yourself or ask
for it to be fixed. There is no follow-up step that repairs this later.

### Commit-authoring work must be delegated

An orchestrating/main Claude Code session must not author commits itself.
Writing the change, crafting the commit message, and opening the PR are
implementation work and belong to a delegated implementation agent. The
orchestrating session's job is to delegate that work, review CI results,
and merge — it does not write code or commit messages directly.

This still leaves the orchestrating session responsible for the
squash-merge title at merge time: it must apply the Conventional Commits
rule above to whichever title it chooses, and copying the PR's title
verbatim is only correct when that title is already conventional.
