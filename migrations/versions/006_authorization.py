"""Habilitação da conta e vínculo autorizado por cartão."""

from alembic import op

revision = "006"
down_revision = "005"


def upgrade():
    op.execute("""
    ALTER TABLE kb_accounts ADD COLUMN enabled boolean NOT NULL DEFAULT true,
      ADD COLUMN import_requested boolean NOT NULL DEFAULT false;
    ALTER TABLE kb_cards ADD COLUMN created_by integer,
      ADD COLUMN conversation_id integer,
      ADD COLUMN conversation_inbox_id integer,
      ADD COLUMN conversation_pinned boolean NOT NULL DEFAULT false;
    UPDATE kb_cards c SET conversation_id=ct.conversation_id,
      conversation_inbox_id=ct.inbox_id FROM kb_contacts ct
      WHERE (c.account_id,c.contact_id)=(ct.account_id,ct.contact_id);
    UPDATE kb_cards c SET created_by=(SELECT h.actor_id FROM kb_history h
      WHERE h.account_id=c.account_id AND h.contact_id=c.contact_id
      AND h.funnel_id=c.funnel_id AND h.action='cartao_criado'
      ORDER BY h.id LIMIT 1);
    CREATE INDEX kb_cards_visibility ON kb_cards
      (account_id,conversation_inbox_id,created_by);
    CREATE VIEW kb_visible_cards AS SELECT c.* FROM kb_cards c
      WHERE c.account_id=nullif(current_setting('kanban.account',true),'')::integer
      AND (current_setting('kanban.role',true)='administrator'
        OR (c.conversation_id IS NULL AND c.created_by=
          nullif(current_setting('kanban.actor',true),'')::integer)
        OR (c.conversation_id IS NOT NULL AND c.conversation_inbox_id IN
          (SELECT value::integer FROM jsonb_array_elements_text(
            coalesce(nullif(current_setting('kanban.inboxes',true),''),'[]')::jsonb))));
    CREATE VIEW kb_visible_history AS SELECT h.* FROM kb_history h
      WHERE h.account_id=nullif(current_setting('kanban.account',true),'')::integer
      AND (current_setting('kanban.role',true)='administrator'
        OR (h.funnel_id IS NOT NULL AND h.contact_id IS NOT NULL AND EXISTS
          (SELECT 1 FROM kb_visible_cards c WHERE c.account_id=h.account_id
          AND c.contact_id=h.contact_id AND c.funnel_id=h.funnel_id))
        OR (h.funnel_id IS NULL AND h.action IN
          ('tarefa_criada','tarefa_editada','tarefa_encerrada','vencimento_atualizado')));
    """)


def downgrade():
    op.execute("DROP VIEW kb_visible_history; DROP VIEW kb_visible_cards")
    op.execute("""
    ALTER TABLE kb_cards DROP COLUMN created_by, DROP COLUMN conversation_id,
      DROP COLUMN conversation_inbox_id, DROP COLUMN conversation_pinned;
    ALTER TABLE kb_accounts DROP COLUMN enabled, DROP COLUMN import_requested;
    """)
