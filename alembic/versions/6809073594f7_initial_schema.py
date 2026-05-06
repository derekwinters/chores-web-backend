"""Initial schema

Revision ID: 6809073594f7
Revises: 
Create Date: 2026-05-05 21:49:09.700349

"""
from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision = '6809073594f7'
down_revision = None
branch_labels = None
depends_on = None


def upgrade() -> None:
    # Create people table
    op.create_table('people',
        sa.Column('id', sa.Integer(), nullable=False),
        sa.Column('name', sa.Text(), nullable=False),
        sa.Column('username', sa.Text(), nullable=False),
        sa.Column('password_hash', sa.Text(), nullable=False),
        sa.Column('is_admin', sa.Integer(), nullable=False, server_default='0'),
        sa.Column('color', sa.Text(), nullable=False, server_default='#004272'),
        sa.Column('goal_7d', sa.Integer(), nullable=False, server_default='20'),
        sa.Column('goal_30d', sa.Integer(), nullable=False, server_default='80'),
        sa.Column('points', sa.Integer(), nullable=False, server_default='0'),
        sa.Column('points_redeemed', sa.Integer(), nullable=False, server_default='0'),
        sa.Column('preferred_theme', sa.Text(), nullable=True),
        sa.PrimaryKeyConstraint('id'),
        sa.UniqueConstraint('username')
    )

    # Create token_blacklist table
    op.create_table('token_blacklist',
        sa.Column('id', sa.Integer(), nullable=False),
        sa.Column('token_jti', sa.Text(), nullable=False),
        sa.Column('invalidated_at', sa.DateTime(timezone=True), nullable=False),
        sa.Column('expires_at', sa.DateTime(timezone=True), nullable=False),
        sa.PrimaryKeyConstraint('id'),
        sa.UniqueConstraint('token_jti')
    )

    # Create chores table
    op.create_table('chores',
        sa.Column('id', sa.Integer(), nullable=False),
        sa.Column('name', sa.Text(), nullable=False),
        sa.Column('schedule_type', sa.Text(), nullable=False),
        sa.Column('schedule_config', sa.JSON(), nullable=False, server_default='{}'),
        sa.Column('assignment_type', sa.Text(), nullable=False, server_default='open'),
        sa.Column('eligible_people', sa.JSON(), nullable=False, server_default='[]'),
        sa.Column('assignee', sa.Text(), nullable=True),
        sa.Column('points', sa.Integer(), nullable=False, server_default='0'),
        sa.Column('state', sa.Text(), nullable=False, server_default='due'),
        sa.Column('disabled', sa.Boolean(), nullable=False, server_default='0'),
        sa.Column('next_due', sa.Date(), nullable=True),
        sa.Column('current_assignee', sa.Text(), nullable=True),
        sa.Column('rotation_index', sa.Integer(), nullable=False, server_default='0'),
        sa.Column('last_changed_at', sa.DateTime(timezone=True), nullable=True),
        sa.Column('last_changed_by', sa.Text(), nullable=True),
        sa.Column('last_change_type', sa.Text(), nullable=True),
        sa.Column('last_completed_at', sa.DateTime(timezone=True), nullable=True),
        sa.Column('last_completed_by', sa.Text(), nullable=True),
        sa.PrimaryKeyConstraint('id')
    )

    # Create points_log table
    op.create_table('points_log',
        sa.Column('id', sa.Integer(), nullable=False),
        sa.Column('person', sa.Text(), nullable=False),
        sa.Column('points', sa.Integer(), nullable=False),
        sa.Column('chore_id', sa.Integer(), nullable=False),
        sa.Column('completed_at', sa.DateTime(timezone=True), nullable=False),
        sa.PrimaryKeyConstraint('id')
    )

    # Create redemption_log table
    op.create_table('redemption_log',
        sa.Column('id', sa.Integer(), nullable=False),
        sa.Column('person_id', sa.Integer(), nullable=False),
        sa.Column('amount', sa.Integer(), nullable=False),
        sa.Column('redeemed_by', sa.Text(), nullable=False),
        sa.Column('timestamp', sa.DateTime(timezone=True), nullable=False),
        sa.PrimaryKeyConstraint('id')
    )

    # Create chore_log table
    op.create_table('chore_log',
        sa.Column('id', sa.Integer(), nullable=False),
        sa.Column('chore_id', sa.Integer(), nullable=False),
        sa.Column('chore_name', sa.Text(), nullable=False),
        sa.Column('person', sa.Text(), nullable=False),
        sa.Column('action', sa.Text(), nullable=False),
        sa.Column('timestamp', sa.DateTime(timezone=True), nullable=False),
        sa.Column('reassigned_to', sa.Text(), nullable=True),
        sa.Column('field_name', sa.Text(), nullable=True),
        sa.Column('old_value', sa.Text(), nullable=True),
        sa.Column('new_value', sa.Text(), nullable=True),
        sa.PrimaryKeyConstraint('id')
    )

    # Create settings table
    op.create_table('settings',
        sa.Column('id', sa.Integer(), nullable=False),
        sa.Column('key', sa.Text(), nullable=False),
        sa.Column('value', sa.Text(), nullable=False),
        sa.PrimaryKeyConstraint('id'),
        sa.UniqueConstraint('key')
    )


def downgrade() -> None:
    op.drop_table('settings')
    op.drop_table('chore_log')
    op.drop_table('redemption_log')
    op.drop_table('points_log')
    op.drop_table('chores')
    op.drop_table('token_blacklist')
    op.drop_table('people')
