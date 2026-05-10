"""Rename content_actor to assignee in chore_log

Revision ID: e5f6a1b2c3d4
Revises: d4e5f6a1b2c3
Create Date: 2026-05-09 00:01:00.000000

"""
from alembic import op


# revision identifiers, used by Alembic.
revision = 'e5f6a1b2c3d4'
down_revision = 'd4e5f6a1b2c3'
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.execute("ALTER TABLE chore_log RENAME COLUMN content_actor TO assignee")


def downgrade() -> None:
    op.execute("ALTER TABLE chore_log RENAME COLUMN assignee TO content_actor")
