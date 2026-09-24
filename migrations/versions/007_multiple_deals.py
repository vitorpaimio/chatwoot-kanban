"""Negociações independentes do mesmo contato no mesmo funil."""

from alembic import op

revision = "007"
down_revision = "006"


def upgrade():
    op.execute("""
    UPDATE kb_history h SET after_state=coalesce(h.after_state,'{}'::jsonb)
      || jsonb_build_object('card_id',c.id)
      FROM kb_cards c WHERE (h.account_id,h.contact_id,h.funnel_id)=
      (c.account_id,c.contact_id,c.funnel_id)
      AND h.after_state->>'card_id' IS NULL;
    ALTER TABLE kb_cards DROP CONSTRAINT
      kb_cards_account_id_funnel_id_contact_id_key;
    CREATE INDEX kb_cards_contact_funnel ON kb_cards
      (account_id,contact_id,funnel_id);
    CREATE OR REPLACE VIEW kb_visible_history AS SELECT h.* FROM kb_history h
      WHERE h.account_id=nullif(current_setting('kanban.account',true),'')::integer
      AND (current_setting('kanban.role',true)='administrator'
        OR (h.funnel_id IS NOT NULL AND h.contact_id IS NOT NULL AND EXISTS
          (SELECT 1 FROM kb_visible_cards c WHERE c.account_id=h.account_id
          AND c.contact_id=h.contact_id AND c.funnel_id=h.funnel_id
          AND c.id::text=h.after_state->>'card_id'))
        OR (h.funnel_id IS NULL AND h.action IN
          ('tarefa_criada','tarefa_editada','tarefa_encerrada','vencimento_atualizado')));
    """)


def downgrade():
    # A restrição falha sem apagar dados se já houver múltiplas negociações.
    op.execute("""
    ALTER TABLE kb_cards ADD CONSTRAINT kb_cards_account_id_funnel_id_contact_id_key
      UNIQUE(account_id,funnel_id,contact_id);
    DROP INDEX kb_cards_contact_funnel;
    CREATE OR REPLACE VIEW kb_visible_history AS SELECT h.* FROM kb_history h
      WHERE h.account_id=nullif(current_setting('kanban.account',true),'')::integer
      AND (current_setting('kanban.role',true)='administrator'
        OR (h.funnel_id IS NOT NULL AND h.contact_id IS NOT NULL AND EXISTS
          (SELECT 1 FROM kb_visible_cards c WHERE c.account_id=h.account_id
          AND c.contact_id=h.contact_id AND c.funnel_id=h.funnel_id))
        OR (h.funnel_id IS NULL AND h.action IN
          ('tarefa_criada','tarefa_editada','tarefa_encerrada','vencimento_atualizado')));
    """)
