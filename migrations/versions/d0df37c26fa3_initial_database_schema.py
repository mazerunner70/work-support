"""Initial database schema

Revision ID: d0df37c26fa3
Revises: 
Create Date: 2025-07-24 20:32:24.933248

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = 'd0df37c26fa3'
down_revision: Union[str, None] = None
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    # ### commands auto generated by Alembic - please adjust! ###
    op.create_table('harvest_jobs',
    sa.Column('id', sa.Integer(), autoincrement=True, nullable=False),
    sa.Column('started_at', sa.DateTime(), nullable=True),
    sa.Column('completed_at', sa.DateTime(), nullable=True),
    sa.Column('status', sa.String(), nullable=True),
    sa.Column('records_processed', sa.Integer(), nullable=True),
    sa.Column('error_message', sa.Text(), nullable=True),
    sa.PrimaryKeyConstraint('id')
    )
    op.create_table('issue_types',
    sa.Column('id', sa.Integer(), nullable=False),
    sa.Column('name', sa.String(), nullable=False),
    sa.Column('url', sa.String(), nullable=True),
    sa.Column('child_type_ids', sa.Text(), nullable=True),
    sa.Column('created_at', sa.DateTime(), nullable=True),
    sa.PrimaryKeyConstraint('id')
    )
    op.create_table('reload_tracking',
    sa.Column('id', sa.Integer(), autoincrement=True, nullable=False),
    sa.Column('reload_started', sa.DateTime(), nullable=True),
    sa.Column('status', sa.String(), nullable=True),
    sa.Column('completed_at', sa.DateTime(), nullable=True),
    sa.Column('records_processed', sa.Integer(), nullable=True),
    sa.Column('error_message', sa.Text(), nullable=True),
    sa.PrimaryKeyConstraint('id')
    )
    op.create_table('team_members',
    sa.Column('id', sa.Integer(), autoincrement=True, nullable=False),
    sa.Column('name', sa.String(), nullable=False),
    sa.Column('jira_id', sa.String(), nullable=False),
    sa.Column('github_id', sa.String(), nullable=False),
    sa.Column('created_at', sa.DateTime(), nullable=True),
    sa.PrimaryKeyConstraint('id')
    )
    op.create_table('issues',
    sa.Column('id', sa.Integer(), autoincrement=True, nullable=False),
    sa.Column('issue_key', sa.String(), nullable=False),
    sa.Column('summary', sa.String(), nullable=True),
    sa.Column('assignee', sa.String(), nullable=True),
    sa.Column('status', sa.String(), nullable=True),
    sa.Column('labels', sa.Text(), nullable=True),
    sa.Column('issue_type_id', sa.Integer(), nullable=True),
    sa.Column('parent_key', sa.String(), nullable=True),
    sa.Column('source', sa.String(), nullable=False),
    sa.Column('created_at', sa.DateTime(), nullable=True),
    sa.Column('updated_at', sa.DateTime(), nullable=True),
    sa.Column('harvested_at', sa.DateTime(), nullable=True),
    sa.ForeignKeyConstraint(['issue_type_id'], ['issue_types.id'], ),
    sa.PrimaryKeyConstraint('id'),
    sa.UniqueConstraint('issue_key')
    )
    # ### end Alembic commands ###


def downgrade() -> None:
    # ### commands auto generated by Alembic - please adjust! ###
    op.drop_table('issues')
    op.drop_table('team_members')
    op.drop_table('reload_tracking')
    op.drop_table('issue_types')
    op.drop_table('harvest_jobs')
    # ### end Alembic commands ###
