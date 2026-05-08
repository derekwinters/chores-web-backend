"""Add update_checks table

Revision ID: a1b2c3d4e5f6
Revises: 9bbbe756fac7
Create Date: 2026-05-07 00:00:00.000000

"""
from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision = 'a1b2c3d4e5f6'
down_revision = '9bbbe756fac7'
branch_labels = None
depends_on = None


def upgrade() -> None:
    # Create update_checks table
    op.create_table(
        'update_checks',
        sa.Column('id', sa.Integer(), nullable=False),
        sa.Column('current_version', sa.Text(), nullable=False),
        sa.Column('latest_version', sa.Text(), nullable=True),
        sa.Column('last_checked_at', sa.DateTime(timezone=True), nullable=True),
        sa.Column('check_enabled', sa.Boolean(), nullable=False, server_default='1'),
        sa.Column('check_interval_hours', sa.Integer(), nullable=False, server_default='24'),
        sa.PrimaryKeyConstraint('id')
    )

    # Create sequence for auto-increment ID
    op.execute("CREATE SEQUENCE IF NOT EXISTS update_checks_id_seq;")
    op.execute("""
        ALTER TABLE update_checks
        ALTER COLUMN id SET DEFAULT nextval('update_checks_id_seq');
    """)


def downgrade() -> None:
    # Drop the update_checks table
    op.drop_table('update_checks')

    # Drop the sequence
    op.execute("DROP SEQUENCE IF EXISTS update_checks_id_seq;")
