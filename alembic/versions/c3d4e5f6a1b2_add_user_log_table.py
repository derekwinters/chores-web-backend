"""Add user_log table

Revision ID: c3d4e5f6a1b2
Revises: b2c3d4e5f6a1
Create Date: 2026-05-09 00:00:00.000000

"""
from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision = 'c3d4e5f6a1b2'
down_revision = 'b2c3d4e5f6a1'
branch_labels = None
depends_on = None


def upgrade() -> None:
    # Create user_log table
    op.create_table(
        'user_log',
        sa.Column('id', sa.Integer(), nullable=False),
        sa.Column('person_id', sa.Integer(), nullable=False),
        sa.Column('person_name', sa.Text(), nullable=False),
        sa.Column('action', sa.Text(), nullable=False),
        sa.Column('field_name', sa.Text(), nullable=True),
        sa.Column('old_value', sa.Text(), nullable=True),
        sa.Column('new_value', sa.Text(), nullable=True),
        sa.Column('changed_by', sa.Text(), nullable=False),
        sa.Column('timestamp', sa.DateTime(timezone=True), nullable=False),
        sa.PrimaryKeyConstraint('id'),
    )

    # Create sequence for auto-increment ID (PostgreSQL only)
    bind = op.get_bind()
    if bind.dialect.name == 'postgresql':
        op.execute("CREATE SEQUENCE IF NOT EXISTS user_log_id_seq;")
        op.execute("""
            ALTER TABLE user_log
            ALTER COLUMN id SET DEFAULT nextval('user_log_id_seq');
        """)


def downgrade() -> None:
    op.drop_table('user_log')

    bind = op.get_bind()
    if bind.dialect.name == 'postgresql':
        op.execute("DROP SEQUENCE IF EXISTS user_log_id_seq;")
