"""Add requires_password_reset column and bcrypt-hash existing passwords

Revision ID: f6a1b2c3d4e5
Revises: e5f6a1b2c3d4
Create Date: 2026-06-05 00:00:00.000000

"""
from alembic import op
import sqlalchemy as sa
from sqlalchemy import text


# revision identifiers, used by Alembic.
revision = 'f6a1b2c3d4e5'
down_revision = 'e5f6a1b2c3d4'
branch_labels = None
depends_on = None


def upgrade() -> None:
    # Add the requires_password_reset column with default False
    op.add_column(
        'people',
        sa.Column('requires_password_reset', sa.Boolean(), nullable=False, server_default='false')
    )

    # Bcrypt-hash all existing plaintext passwords and set requires_password_reset = True
    bind = op.get_bind()
    import bcrypt as _bcrypt

    result = bind.execute(text("SELECT id, password_hash FROM people"))
    rows = result.fetchall()
    for row in rows:
        person_id, plaintext = row[0], row[1]
        hashed = _bcrypt.hashpw(plaintext.encode("utf-8"), _bcrypt.gensalt(rounds=12)).decode("utf-8")
        bind.execute(
            text("UPDATE people SET password_hash = :hash, requires_password_reset = true WHERE id = :id"),
            {"hash": hashed, "id": person_id}
        )


def downgrade() -> None:
    op.drop_column('people', 'requires_password_reset')
