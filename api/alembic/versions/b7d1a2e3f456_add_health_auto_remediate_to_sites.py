"""add health_auto_remediate to sites

Revision ID: b7d1a2e3f456
Revises: a3c8e7f91d42
Create Date: 2026-03-01 23:30:00.000000

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa

# revision identifiers, used by Alembic.
revision: str = 'b7d1a2e3f456'
down_revision: Union[str, None] = 'a3c8e7f91d42'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.add_column(
        'sites',
        sa.Column(
            'health_auto_remediate',
            sa.Boolean(),
            server_default=sa.text('false'),
            nullable=False,
        ),
    )


def downgrade() -> None:
    op.drop_column('sites', 'health_auto_remediate')
