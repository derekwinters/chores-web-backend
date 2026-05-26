# Developer Setup & Workflow

## Prerequisites

- Node.js 16+ (for frontend)
- Python 3.11+ (for backend)
- Git

## Local Development Setup

### Backend Setup

```bash
# Navigate to backend directory
cd backend

# Create virtual environment
python -m venv venv

# Activate virtual environment
# On macOS/Linux:
source venv/bin/activate
# On Windows:
venv\Scripts\activate

# Install dependencies
pip install -r requirements.txt

# Run development server
uvicorn app.main:app --reload --host 0.0.0.0 --port 8000
```

**Swagger UI:** http://localhost:8000/docs

### Frontend Setup

```bash
# Navigate to frontend directory
cd frontend

# Install dependencies
npm install

# Run development server
npm run dev
```

**Development URL:** http://localhost:5173

### First-Time Setup

1. Start backend (opens on :8000)
2. Start frontend (opens on :5173)
3. Frontend will redirect to setup page if no users exist
4. Create first admin user through setup page
5. Login with created credentials

## Issue Lifecycle

All work in this repository follows a 4-stage lifecycle controlled by GitHub issue labels.

### Stages

| Stage | Label | Description |
|-------|-------|-------------|
| 1. Concept | *(none)* | Raw idea recorded, not yet triaged |
| 2. Context & Assignment | `ready-to-grill` | Triage complete, milestone assigned |
| 3. Grilling Complete | `ready-for-work` | Grilling done, implementation contract exists |
| 4. In Development | `in-development` | Agent actively working on the issue |

A stage must not begin unless the proper label is assigned.

### Agents & Entry Points

| Agent | Trigger | Action |
|-------|---------|--------|
| `github-issue-triage-orchestrator` | Manual or webhook | Triages issue, assigns milestone, applies `ready-to-grill` |
| `/grill-with-docs issue <N>` | Manual | Runs grilling session, posts structured comment, flips label to `ready-for-work` |
| `github-issue-implementation-orchestrator` | Manual | Implements issue end-to-end via TDD, creates PR |

### Grilling

Grilling is required before development begins. Run `/grill-with-docs issue <N>` to:

1. Conduct a structured session covering all 4 areas: backend, database, frontend, docs
2. Post a structured grilling comment on the issue (decisions, impact areas, behaviors checklist)
3. Remove `ready-to-grill`, apply `ready-for-work`

### Development

The implementation orchestrator handles all development autonomously:

1. Validates `ready-for-work` label and grilling comment presence
2. Creates `<type>-issue-<N>` branch from updated main
3. Drafts documentation updates (`docs:` commit)
4. Runs TDD loop — derives behaviors from grilling checklist, red-green-refactor cycles
5. Full test suite must pass
6. Docker verify + user approval pause
7. Code commit (`feat:/fix:/refactor:`)
8. Doc-validate — reconciles docs against implementation
9. Push + PR creation (removes `in-development`)

## Development Workflow

### Running Tests

**Frontend:**
```bash
cd frontend
npm test                 # Watch mode
npm test -- --run      # Single run
```

**Tests must pass before committing.**

### Making Changes

1. **Frontend Changes:**
   - Edit components/pages in `src/`
   - Tests automatically re-run
   - Ensure tests pass: `npm test -- --run`
   - Commit only if tests pass (205/205)

2. **Backend Changes:**
   - Edit routers/services in `app/`
   - Server auto-reloads with `--reload`
   - Test via Swagger UI or API client
   - Add appropriate logging to ChoreLog
   - Ensure database migrations work

3. **Database Schema Changes:**
   - Add/modify fields in `models.py`
   - Update corresponding schemas in `schemas.py`
   - Tables auto-create on startup (see `lifespan` in `main.py`)
   - Add migration scripts if needed for existing data

### Commit Guidelines

- **Title:** Short, imperative mood ("add feature", "fix bug", "refactor component")
- **Body:** Explain *why* not *what* (code shows what)
- **Test Status:** Include "Frontend tests: 205/205 passing ✓" if applicable
- **Co-authored:** End with "Co-Authored-By: Claude Haiku 4.5 <noreply@anthropic.com>"

Example:
```
feat: add theme deletion for custom themes

- Add DELETE /theme/delete/{theme_id} endpoint
- Prevent deletion of default themes (dark, light, ocean)
- Switch to dark theme if current is deleted
- Add confirmation modal in ThemeSettings component
- Add 3 tests for deletion functionality

Frontend tests: 205/205 passing ✓

Co-Authored-By: Claude Haiku 4.5 <noreply@anthropic.com>
```

## Upgrade Regression Test

The upgrade regression test validates that data seeded against a previous release migrates correctly when the new backend starts against the same Postgres volume. It runs as a CI job on every PR to `main`.

### How It Works

1. **Pull previous release**: The job resolves the latest published GHCR tag dynamically at runtime.
2. **Start old backend + Postgres**: Brings up `docker-compose.test-upgrade.yml` with the previous release image.
3. **Seed comprehensive data**: Runs `backend/seed.py` against the old backend — creates People, Chores, Completions, Skips, Reassignments, and Amendments.
4. **Start new backend**: Builds the backend image from the current branch and starts it against the same Postgres volume after seeding completes.
5. **Validate**: Runs `backend/validate_upgrade.py` — API assertions (entity counts, assignees, points log, activity log, health) plus raw SQL FK/count integrity checks.
6. **Result**: Non-zero exit on any failure fails the CI job.

### Files

| File | Purpose |
|------|---------|
| `docker-compose.test-upgrade.yml` | Upgrade test orchestration: Postgres + old backend + new backend services |
| `backend/seed.py` | Comprehensive seeding: auth login + People, Chores, Completions, Skips, Reassignments, Amendments |
| `backend/validate_upgrade.py` | Validation script: API assertions + raw SQL FK/count checks |
| `.github/workflows/test.yml` | CI: `upgrade-regression` job added, triggered on PRs to `main` |

### Running Locally

```bash
# Resolve the latest GHCR tag
PREV_TAG=$(gh release list --limit 1 --json tagName -q '.[0].tagName')

# Run the upgrade test
PREV_TAG=$PREV_TAG docker compose -f docker-compose.test-upgrade.yml up \
  --build \
  --abort-on-container-exit \
  --exit-code-from validate
```

### Failure Mode

The job exits non-zero and fails CI. Check the `validate` service logs for specific assertion failures.

## Release Notes

Release notes live in the MkDocs blog at `docs/blog/posts/`. Each release requires a corresponding blog post before the release PR can merge.

### File Naming

Release notes files must follow this naming convention:

```
docs/blog/posts/release-v{VERSION}.md
```

For example, for version `1.7.0`: `docs/blog/posts/release-v1.7.0.md`.

### CI Enforcement

The `release-notes` CI job in `.github/workflows/test.yml` runs on every pull request. It detects release PRs by title pattern `chore(main): release v*` and fails if the corresponding release notes file is missing. Non-release PRs skip the check automatically.

### Creating Release Notes

Create the blog post file before or alongside the release PR:

```bash
# For version v1.7.0
cat > docs/blog/posts/release-v1.7.0.md << 'EOF'
---
date: 2026-01-01
---

# Release v1.7.0

Summary of changes in this release.
EOF
```
