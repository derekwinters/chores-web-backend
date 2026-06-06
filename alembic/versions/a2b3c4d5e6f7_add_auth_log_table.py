"""Add auth_log table for authentication event auditing

Revision ID: a2b3c4d5e6f7
Revises: f6a1b2c3d4e5
Create Date: 2026-06-05 00:01:00.000000

"""
from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision = 'a2b3c4d5e6f7'
down_revision = 'f6a1b2c3d4e5'
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        'auth_log',
        sa.Column('id', sa.Integer(), nullable=False),
        sa.Column('username', sa.Text(), nullable=False),
        sa.Column('action', sa.Text(), nullable=False),
        sa.Column('changed_by', sa.Text(), nullable=True),
        sa.Column('timestamp', sa.DateTime(timezone=True), nullable=False),
        sa.PrimaryKeyConstraint('id'),
    )
    op.create_index('ix_auth_log_username', 'auth_log', ['username'])
    op.create_index('ix_auth_log_action', 'auth_log', ['action'])
    op.create_index('ix_auth_log_timestamp', 'auth_log', ['timestamp'])


def downgrade() -> None:
    op.drop_index('ix_auth_log_timestamp', 'auth_log')
    op.drop_index('ix_auth_log_action', 'auth_log')
    op.drop_index('ix_auth_log_username', 'auth_log')
    op.drop_table('auth_log')
