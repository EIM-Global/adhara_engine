"""add preview environments

Revision ID: a3c8e7f91d42
Revises: 0f849556d1b9
Create Date: 2026-03-01 18:00:00.000000

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

# revision identifiers, used by Alembic.
revision: str = 'a3c8e7f91d42'
down_revision: Union[str, None] = '0f849556d1b9'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.create_table('preview_environments',
        sa.Column('id', sa.UUID(), nullable=False),
        sa.Column('site_id', sa.UUID(), nullable=False),
        sa.Column('tenant_id', sa.UUID(), nullable=False),
        sa.Column('pr_number', sa.Integer(), nullable=False),
        sa.Column('pr_title', sa.String(length=512), nullable=True),
        sa.Column('pr_author', sa.String(length=255), nullable=True),
        sa.Column('pr_branch', sa.String(length=255), nullable=False),
        sa.Column('pr_url', sa.String(length=1024), nullable=True),
        sa.Column('git_provider', sa.String(length=32), nullable=False),
        sa.Column('commit_sha', sa.String(length=64), nullable=True),
        sa.Column('pipeline_run_id', sa.UUID(), nullable=True),
        sa.Column('status', sa.String(length=32), nullable=True),
        sa.Column('container_id', sa.String(length=255), nullable=True),
        sa.Column('host_port', sa.Integer(), nullable=True),
        sa.Column('preview_url', sa.String(length=1024), nullable=True),
        sa.Column('image_tag', sa.String(length=512), nullable=True),
        sa.Column('ttl_hours', sa.Integer(), nullable=True),
        sa.Column('pr_state', sa.String(length=32), nullable=True),
        sa.Column('destroy_reason', sa.String(length=64), nullable=True),
        sa.Column('created_at', sa.DateTime(timezone=True), server_default=sa.text('now()'), nullable=False),
        sa.Column('updated_at', sa.DateTime(timezone=True), nullable=True),
        sa.Column('destroyed_at', sa.DateTime(timezone=True), nullable=True),
        sa.ForeignKeyConstraint(['pipeline_run_id'], ['pipeline_runs.id'], ondelete='SET NULL'),
        sa.ForeignKeyConstraint(['site_id'], ['sites.id'], ondelete='CASCADE'),
        sa.ForeignKeyConstraint(['tenant_id'], ['tenants.id'], ondelete='CASCADE'),
        sa.PrimaryKeyConstraint('id'),
    )
    op.create_index(op.f('ix_preview_environments_site_id'), 'preview_environments', ['site_id'], unique=False)
    op.create_index(op.f('ix_preview_environments_tenant_id'), 'preview_environments', ['tenant_id'], unique=False)
    op.create_index(op.f('ix_preview_environments_status'), 'preview_environments', ['status'], unique=False)


def downgrade() -> None:
    op.drop_index(op.f('ix_preview_environments_status'), table_name='preview_environments')
    op.drop_index(op.f('ix_preview_environments_tenant_id'), table_name='preview_environments')
    op.drop_index(op.f('ix_preview_environments_site_id'), table_name='preview_environments')
    op.drop_table('preview_environments')
