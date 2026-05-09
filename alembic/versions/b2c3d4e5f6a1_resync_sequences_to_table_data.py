"""Resync sequences to table data

Revision ID: b2c3d4e5f6a1
Revises: a1b2c3d4e5f6
Create Date: 2026-05-09 00:00:00.000000

"""
from alembic import op


# revision identifiers, used by Alembic.
revision = 'b2c3d4e5f6a1'
down_revision = 'a1b2c3d4e5f6'
branch_labels = None
depends_on = None


def upgrade() -> None:
    # Only run on PostgreSQL — SQLite does not have sequences
    bind = op.get_bind()
    if bind.dialect.name != 'postgresql':
        return

    tables = [
        'people',
        'token_blacklist',
        'chores',
        'points_log',
        'redemption_log',
        'chore_log',
        'settings',
        'update_checks',
    ]

    for table in tables:
        # Advance sequence to GREATEST(MAX(id), last_value) so it only moves forward.
        # COALESCE handles empty tables where MAX(id) is NULL.
        op.execute(f"""
            SELECT SETVAL(
                '{table}_id_seq',
                GREATEST(
                    COALESCE((SELECT MAX(id) FROM {table}), 0),
                    (SELECT last_value FROM {table}_id_seq)
                )
            );
        """)


def downgrade() -> None:
    # Sequences cannot be safely wound back — downgrade is a no-op
    pass
