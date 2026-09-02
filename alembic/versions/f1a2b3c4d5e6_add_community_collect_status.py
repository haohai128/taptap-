"""add community collect_status

Revision ID: f1a2b3c4d5e6
Revises: c8f3e75b8018
Create Date: 2026-08-26 10:30:00.000000

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa
import sqlmodel  # noqa: F401


# revision identifiers, used by Alembic.
revision: str = 'f1a2b3c4d5e6'
down_revision: Union[str, Sequence[str], None] = 'c8f3e75b8018'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """Upgrade schema."""
    with op.batch_alter_table('community', schema=None) as batch_op:
        batch_op.add_column(
            sa.Column(
                'collect_status',
                sqlmodel.sql.sqltypes.AutoString(),
                nullable=False,
                server_default='enabled',
            )
        )
        batch_op.create_index('ix_community_collect_status', ['collect_status'], unique=False)


def downgrade() -> None:
    """Downgrade schema."""
    with op.batch_alter_table('community', schema=None) as batch_op:
        batch_op.drop_index('ix_community_collect_status', table_name='community')
        batch_op.drop_column('collect_status')
