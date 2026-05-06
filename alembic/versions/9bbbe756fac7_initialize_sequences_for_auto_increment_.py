"""Initialize sequences for auto-increment IDs

Revision ID: 9bbbe756fac7
Revises: 6809073594f7
Create Date: 2026-05-05 22:16:21.124305

"""
from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision = '9bbbe756fac7'
down_revision = '6809073594f7'
branch_labels = None
depends_on = None


def upgrade() -> None:
    # For each table with auto-increment ID, create sequence if needed and set nextval
    tables = [
        'people',
        'token_blacklist',
        'chores',
        'points_log',
        'redemption_log',
        'chore_log',
        'settings'
    ]

    for table in tables:
        # Create sequence if it doesn't exist
        op.execute(f"""
            CREATE SEQUENCE IF NOT EXISTS {table}_id_seq;
        """)

        # Get max ID from table (handle empty tables)
        op.execute(f"""
            SELECT SETVAL('{table}_id_seq',
                COALESCE((SELECT MAX(id) FROM {table}), 0) + 1
            );
        """)

        # Bind sequence to column (idempotent, will fail silently if already bound)
        op.execute(f"""
            ALTER TABLE {table}
            ALTER COLUMN id SET DEFAULT nextval('{table}_id_seq');
        """)


def downgrade() -> None:
    # Drop sequences
    tables = [
        'people',
        'token_blacklist',
        'chores',
        'points_log',
        'redemption_log',
        'chore_log',
        'settings'
    ]

    for table in tables:
        op.execute(f"DROP SEQUENCE IF EXISTS {table}_id_seq;")
        op.execute(f"""
            ALTER TABLE {table}
            ALTER COLUMN id DROP DEFAULT;
        """)
