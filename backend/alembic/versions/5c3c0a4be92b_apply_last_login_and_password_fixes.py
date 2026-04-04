"""Apply last_login columns and password length fixes.

Revision ID: 5c3c0a4be92b
Revises: 0d076625d74d
Create Date: 2026-03-31 12:05:00.000000
"""

from typing import Sequence, Union

from alembic import op


revision: str = "5c3c0a4be92b"
down_revision: Union[str, Sequence[str], None] = "0d076625d74d"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.execute("ALTER TABLE IF EXISTS clinician ADD COLUMN IF NOT EXISTS last_login TIMESTAMP NULL")
    op.execute("ALTER TABLE IF EXISTS clinician ADD COLUMN IF NOT EXISTS last_simulation_at TIMESTAMP NULL")
    op.execute("ALTER TABLE IF EXISTS patient ADD COLUMN IF NOT EXISTS last_login TIMESTAMP NULL")
    op.execute("ALTER TABLE IF EXISTS patient ADD COLUMN IF NOT EXISTS last_simulation_at TIMESTAMP NULL")
    op.execute('ALTER TABLE IF EXISTS "user" ADD COLUMN IF NOT EXISTS last_login TIMESTAMP NULL')
    op.execute('ALTER TABLE IF EXISTS "user" ADD COLUMN IF NOT EXISTS last_simulation_at TIMESTAMP NULL')
    op.execute("ALTER TABLE IF EXISTS clinician ALTER COLUMN password TYPE VARCHAR(255)")
    op.execute("ALTER TABLE IF EXISTS ituser ALTER COLUMN password TYPE VARCHAR(255)")


def downgrade() -> None:
    op.execute("ALTER TABLE IF EXISTS clinician ALTER COLUMN password TYPE VARCHAR(40)")
    op.execute("ALTER TABLE IF EXISTS ituser ALTER COLUMN password TYPE VARCHAR(40)")
    op.execute('ALTER TABLE IF EXISTS "user" DROP COLUMN IF EXISTS last_simulation_at')
    op.execute('ALTER TABLE IF EXISTS "user" DROP COLUMN IF EXISTS last_login')
    op.execute("ALTER TABLE IF EXISTS patient DROP COLUMN IF EXISTS last_simulation_at")
    op.execute("ALTER TABLE IF EXISTS patient DROP COLUMN IF EXISTS last_login")
    op.execute("ALTER TABLE IF EXISTS clinician DROP COLUMN IF EXISTS last_simulation_at")
    op.execute("ALTER TABLE IF EXISTS clinician DROP COLUMN IF EXISTS last_login")
