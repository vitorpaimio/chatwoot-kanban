"""Criação automática de negociações por funil para novos leads."""

from alembic import op

revision = "013"
down_revision = "012"


def upgrade():
    op.execute("""
        ALTER TABLE kb_funnels
          ADD COLUMN auto_create_stage_id bigint,
          ADD COLUMN auto_create_inboxes integer[] NOT NULL DEFAULT '{}',
          ADD CONSTRAINT kb_funnel_auto_stage
            FOREIGN KEY(account_id,id,auto_create_stage_id)
            REFERENCES kb_stages(account_id,funnel_id,id)
            ON DELETE SET NULL (auto_create_stage_id);
    """)


def downgrade():
    op.execute("""
        ALTER TABLE kb_funnels DROP CONSTRAINT kb_funnel_auto_stage,
          DROP COLUMN auto_create_inboxes, DROP COLUMN auto_create_stage_id
    """)
