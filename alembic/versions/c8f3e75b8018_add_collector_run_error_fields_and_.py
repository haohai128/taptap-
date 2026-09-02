"""add collector run error fields and attempt status

Revision ID: c8f3e75b8018
Revises: af8a18c3e1f5
Create Date: 2026-08-26 09:57:36.056048

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa
import sqlmodel  # noqa: F401


# revision identifiers, used by Alembic.
revision: str = 'c8f3e75b8018'
down_revision: Union[str, Sequence[str], None] = 'af8a18c3e1f5'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """Upgrade schema."""
    with op.batch_alter_table('analysisattempt', schema=None) as batch_op:
        batch_op.add_column(sa.Column('status', sqlmodel.sql.sqltypes.AutoString(), nullable=False, server_default='retryable'))

    with op.batch_alter_table('collectionrun', schema=None) as batch_op:
        batch_op.add_column(sa.Column('last_request_at', sa.DateTime(), nullable=True))
        batch_op.add_column(sa.Column('error_type', sqlmodel.sql.sqltypes.AutoString(), nullable=True))


def downgrade() -> None:
    """Downgrade schema."""
    with op.batch_alter_table('collectionrun', schema=None) as batch_op:
        batch_op.drop_column('error_type')
        batch_op.drop_column('last_request_at')

    with op.batch_alter_table('analysisattempt', schema=None) as batch_op:
        batch_op.drop_column('status')
