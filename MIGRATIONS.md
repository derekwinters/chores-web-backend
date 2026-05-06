# Database Migrations

This project uses **Alembic** to manage database schema changes in a version-controlled way.

## Structure

- `alembic/` - Alembic configuration and migration scripts
  - `versions/` - Migration files (one per schema change)
  - `env.py` - Alembic environment configuration
- `alembic.ini` - Alembic configuration file with database URL

## Running Migrations

### During App Startup

Migrations run automatically when the app starts:
```bash
python -m uvicorn app.main:app --reload
```

The `apply_migrations()` function in `app/migrations.py` runs `alembic upgrade head` on startup.

### Manual Migration

To manually run migrations:
```bash
cd backend
python -m alembic upgrade head
```

## Creating New Migrations

### Auto-generate Migration

After modifying models in `app/models.py`:

```bash
cd backend
python -m alembic revision --autogenerate -m "Description of change"
```

This inspects the current schema and model definitions, then generates a migration file.

### Manual Migration

For complex changes or when autogenerate doesn't capture everything:

```bash
cd backend
python -m alembic revision -m "Description of change"
```

Then edit the generated file in `alembic/versions/` to add your upgrade/downgrade logic.

## Checking Migration Status

```bash
cd backend
python -m alembic current  # Show current revision
python -m alembic history  # Show all revisions
```

## Downgrading

To roll back migrations:

```bash
cd backend
python -m alembic downgrade -1  # Roll back one migration
python -m alembic downgrade <revision>  # Roll back to specific revision
```

## Notes

- Migrations are applied with `Mapped` columns matching `models.py`
- Each migration file is tracked in git — include in commits
- Always test migrations locally before deploying
- Downgrade logic should be implemented for reversibility
- Database URL is loaded from `app/config.py` (uses `DATABASE_URL` env var)
