"""Add last_login and last_simulation_at to clinician

Revision ID: 0d076625d74d
Revises: 
Create Date: 2026-03-30 20:41:10.322128

"""
from typing import Sequence, Union

from alembic import op


# revision identifiers, used by Alembic.
revision: str = '0d076625d74d'
down_revision: Union[str, Sequence[str], None] = None
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    pass


def downgrade() -> None:
    pass
