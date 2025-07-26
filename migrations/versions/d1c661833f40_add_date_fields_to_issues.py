"""add_date_fields_to_issues

Revision ID: d1c661833f40
Revises: 61a4075d8531
Create Date: 2025-07-26 10:37:14.530928

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = 'd1c661833f40'
down_revision: Union[str, None] = '61a4075d8531'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    # Add date columns to issues table
    op.add_column('issues', sa.Column('start_date', sa.DateTime(), nullable=True))
    op.add_column('issues', sa.Column('transition_date', sa.DateTime(), nullable=True))
    op.add_column('issues', sa.Column('end_date', sa.DateTime(), nullable=True))


def downgrade() -> None:
    # Remove date columns from issues table
    op.drop_column('issues', 'end_date')
    op.drop_column('issues', 'transition_date')
    op.drop_column('issues', 'start_date')
