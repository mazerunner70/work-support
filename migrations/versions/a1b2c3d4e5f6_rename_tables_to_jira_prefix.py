"""rename_tables_to_jira_prefix

Revision ID: a1b2c3d4e5f6
Revises: e7g9h1i3j5k7
Create Date: 2025-01-15 14:30:00.000000

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = 'a1b2c3d4e5f6'
down_revision: Union[str, None] = 'e7g9h1i3j5k7'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    # SQLite doesn't support dropping foreign keys directly, so we'll use a simplified approach
    # Since we're just renaming tables, SQLite will automatically update foreign key references
    
    # Rename tables
    op.rename_table('issues', 'jira_issues')
    op.rename_table('changelogs', 'jira_changelogs')


def downgrade() -> None:
    # Rename tables back to original names
    op.rename_table('jira_issues', 'issues')
    op.rename_table('jira_changelogs', 'changelogs') 