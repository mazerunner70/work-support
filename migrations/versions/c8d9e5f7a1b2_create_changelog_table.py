"""create_changelog_table

Revision ID: c8d9e5f7a1b2
Revises: f2a7b9c8d1e5
Create Date: 2025-01-15 10:30:00.000000

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = 'c8d9e5f7a1b2'
down_revision: Union[str, None] = 'f2a7b9c8d1e5'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    # Create changelogs table
    op.create_table('changelogs',
        sa.Column('id', sa.Integer(), autoincrement=True, nullable=False),
        sa.Column('issue_id', sa.String(), nullable=False),
        sa.Column('jira_changelog_id', sa.String(), nullable=False),
        sa.Column('field_name', sa.String(), nullable=False),
        sa.Column('from_value', sa.Text(), nullable=True),
        sa.Column('to_value', sa.Text(), nullable=True),
        sa.Column('from_display', sa.Text(), nullable=True),
        sa.Column('to_display', sa.Text(), nullable=True),
        sa.Column('created_at', sa.DateTime(), nullable=False),
        sa.Column('harvested_at', sa.DateTime(), nullable=True),
        sa.ForeignKeyConstraint(['issue_id'], ['issues.issue_id'], ),
        sa.PrimaryKeyConstraint('id')
    )
    
    # Create indexes for efficient querying
    op.create_index('ix_changelogs_created_at', 'changelogs', ['created_at'], unique=False)
    op.create_index('ix_changelogs_issue_created', 'changelogs', ['issue_id', 'created_at'], unique=False)
    op.create_index('ix_changelogs_field', 'changelogs', ['field_name'], unique=False)


def downgrade() -> None:
    # Drop indexes and table
    op.drop_index('ix_changelogs_field', table_name='changelogs')
    op.drop_index('ix_changelogs_issue_created', table_name='changelogs')
    op.drop_index('ix_changelogs_created_at', table_name='changelogs')
    op.drop_table('changelogs') 