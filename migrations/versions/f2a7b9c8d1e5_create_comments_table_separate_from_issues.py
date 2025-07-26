"""create_comments_table_separate_from_issues

Revision ID: f2a7b9c8d1e5
Revises: bb257883e1e3
Create Date: 2025-01-15 10:00:00.000000

"""
from typing import Sequence, Union
import json

from alembic import op
import sqlalchemy as sa
from sqlalchemy import text


# revision identifiers, used by Alembic.
revision: str = 'f2a7b9c8d1e5'
down_revision: Union[str, None] = 'bb257883e1e3'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    # Create comments table
    op.create_table('comments',
        sa.Column('id', sa.Integer(), autoincrement=True, nullable=False),
        sa.Column('issue_key', sa.String(), nullable=False),
        sa.Column('body', sa.Text(), nullable=False),
        sa.Column('created_at', sa.DateTime(), nullable=False),
        sa.Column('updated_at', sa.DateTime(), nullable=True),
        sa.Column('jira_comment_id', sa.String(), nullable=True),
        sa.ForeignKeyConstraint(['issue_key'], ['issues.issue_key'], ),
        sa.PrimaryKeyConstraint('id')
    )
    op.create_index('ix_comments_created_at', 'comments', ['created_at'], unique=False)
    op.create_index('ix_comments_issue_created', 'comments', ['issue_key', 'created_at'], unique=False)

    # Migrate existing comment data from JSON column to new table
    connection = op.get_bind()
    
    # Get all issues with comments
    result = connection.execute(text("SELECT issue_key, comments FROM issues WHERE comments IS NOT NULL AND comments != ''"))
    
    for row in result:
        issue_key, comments_json = row
        if comments_json:
            try:
                comments = json.loads(comments_json)
                for comment in comments:
                    if isinstance(comment, dict) and comment.get('body'):
                        connection.execute(text("""
                            INSERT INTO comments (issue_key, body, created_at, updated_at)
                            VALUES (:issue_key, :body, :created_at, :updated_at)
                        """), {
                            'issue_key': issue_key,
                            'body': comment.get('body', ''),
                            'created_at': comment.get('created') or comment.get('created_at'),
                            'updated_at': comment.get('updated') or comment.get('updated_at')
                        })
            except (json.JSONDecodeError, TypeError) as e:
                # Skip malformed comment data
                continue


def downgrade() -> None:
    # Migrate comments back to JSON column (basic version)
    connection = op.get_bind()
    
    # Get all comments grouped by issue_key
    result = connection.execute(text("""
        SELECT issue_key, 
               json_group_array(
                   json_object(
                       'body', body,
                       'created', created_at,
                       'updated', updated_at
                   )
               ) as comments_json
        FROM comments 
        GROUP BY issue_key
    """))
    
    for row in result:
        issue_key, comments_json = row
        connection.execute(text("""
            UPDATE issues 
            SET comments = :comments_json 
            WHERE issue_key = :issue_key
        """), {
            'issue_key': issue_key,
            'comments_json': comments_json
        })
    
    # Drop comments table and indexes
    op.drop_index('ix_comments_issue_created', table_name='comments')
    op.drop_index('ix_comments_created_at', table_name='comments')
    op.drop_table('comments') 