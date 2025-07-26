"""add_team_field_to_issues

Revision ID: 61a4075d8531
Revises: bf638c72e3b1
Create Date: 2025-07-26 10:29:52.740778

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = '61a4075d8531'
down_revision: Union[str, None] = 'bf638c72e3b1'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    # Add team column to issues table
    op.add_column('issues', sa.Column('team', sa.String(), nullable=True))


def downgrade() -> None:
    # Remove team column from issues table
    op.drop_column('issues', 'team')
