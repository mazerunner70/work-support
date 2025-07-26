"""create_changes_log_table

Revision ID: e7g9h1i3j5k7
Revises: d4f6a8b9c2e1
Create Date: 2025-01-15 11:30:00.000000

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = 'e7g9h1i3j5k7'
down_revision: Union[str, None] = 'd4f6a8b9c2e1'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    # Create changes_log table
    op.create_table('changes_log',
        sa.Column('id', sa.Integer(), autoincrement=True, nullable=False),
        sa.Column('issue_key', sa.String(), nullable=False),
        sa.Column('timestamp', sa.DateTime(), nullable=False),
        sa.Column('field_name', sa.String(), nullable=False),
        sa.Column('updated_value', sa.Text(), nullable=True),
        sa.Column('change_type', sa.String(), nullable=False),
        sa.ForeignKeyConstraint(['issue_key'], ['issues.issue_key'], ),
        sa.PrimaryKeyConstraint('id')
    )
    
    # Create indexes for efficient querying
    op.create_index('ix_changes_log_timestamp', 'changes_log', ['timestamp'], unique=False)
    op.create_index('ix_changes_log_issue_timestamp', 'changes_log', ['issue_key', 'timestamp'], unique=False)
    op.create_index('ix_changes_log_field', 'changes_log', ['field_name'], unique=False)


def downgrade() -> None:
    # Drop indexes and table
    op.drop_index('ix_changes_log_field', table_name='changes_log')
    op.drop_index('ix_changes_log_issue_timestamp', table_name='changes_log')
    op.drop_index('ix_changes_log_timestamp', table_name='changes_log')
    op.drop_table('changes_log') 