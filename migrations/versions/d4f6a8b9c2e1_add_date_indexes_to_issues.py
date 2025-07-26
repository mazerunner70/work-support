"""add_date_indexes_to_issues

Revision ID: d4f6a8b9c2e1
Revises: c8d9e5f7a1b2
Create Date: 2025-01-15 11:00:00.000000

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = 'd4f6a8b9c2e1'
down_revision: Union[str, None] = 'c8d9e5f7a1b2'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    # Add date indexes to issues table
    op.create_index('ix_issues_start_date', 'issues', ['start_date'], unique=False)
    op.create_index('ix_issues_transition_date', 'issues', ['transition_date'], unique=False)
    op.create_index('ix_issues_end_date', 'issues', ['end_date'], unique=False)


def downgrade() -> None:
    # Drop date indexes from issues table
    op.drop_index('ix_issues_end_date', table_name='issues')
    op.drop_index('ix_issues_transition_date', table_name='issues')
    op.drop_index('ix_issues_start_date', table_name='issues') 