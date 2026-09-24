"""Responsável independente da tarefa e índice ordenado do quadro."""

from alembic import op

revision = "012"
down_revision = "011"


def upgrade():
    op.execute("""
        ALTER TABLE kb_tasks ADD COLUMN assigned_to integer;
        UPDATE kb_tasks SET assigned_to=created_by;
        ALTER TABLE kb_tasks ADD CONSTRAINT kb_task_assignee
          FOREIGN KEY(account_id,assigned_to) REFERENCES kb_agents(account_id,user_id);
        CREATE INDEX kb_cards_page ON kb_cards
          (account_id,funnel_id,stage_id,position,id);
    """)


def downgrade():
    op.execute("DROP INDEX kb_cards_page; ALTER TABLE kb_tasks DROP COLUMN assigned_to")
