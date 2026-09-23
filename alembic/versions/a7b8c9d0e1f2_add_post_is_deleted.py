"""add post is_deleted flag

Revision ID: a7b8c9d0e1f2
Revises: f1a2b3c4d5e6
Create Date: 2026-09-14 12:00:00.000000

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = 'a7b8c9d0e1f2'
down_revision: Union[str, Sequence[str], None] = 'f1a2b3c4d5e6'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """Upgrade schema."""
    with op.batch_alter_table('post', schema=None) as batch_op:
        batch_op.add_column(
            sa.Column(
                'is_deleted',
                sa.Boolean(),
                nullable=False,
                server_default=sa.text('0'),
            )
        )
        batch_op.create_index('ix_post_is_deleted', ['is_deleted'], unique=False)


def downgrade() -> None:
    """Downgrade schema."""
    with op.batch_alter_table('post', schema=None) as batch_op:
        batch_op.drop_index('ix_post_is_deleted', batch_op.f('ix_post_is_deleted'))
        batch_op.drop_column('is_deleted')
