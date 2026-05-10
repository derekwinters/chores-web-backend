"""Add content_actor to chore_log

Revision ID: d4e5f6a1b2c3
Revises: c3d4e5f6a1b2
Create Date: 2026-05-09 00:00:00.000000

"""
from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision = 'd4e5f6a1b2c3'
down_revision = 'c3d4e5f6a1b2'
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column(
        'chore_log',
        sa.Column('content_actor', sa.Text(), nullable=True)
    )


def downgrade() -> None:
    op.drop_column('chore_log', 'content_actor')
