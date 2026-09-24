"""Exclusão recuperável de negociações sem apagar contato ou histórico."""

import sqlalchemy as sa
from alembic import op

revision = "008"
down_revision = "007"


def upgrade():
    definition = (
        op.get_bind()
        .execute(sa.text("SELECT pg_get_viewdef('kb_visible_cards'::regclass, true)"))
        .scalar_one()
        .rstrip("; \n")
    )
    op.execute("CREATE VIEW kb_authorized_cards AS " + definition)
    op.execute("""
        CREATE TABLE kb_card_deletions (
          account_id integer NOT NULL, card_id bigint NOT NULL,
          deleted_at timestamptz NOT NULL DEFAULT now(),
          PRIMARY KEY(account_id,card_id),
          FOREIGN KEY(account_id,card_id) REFERENCES kb_cards(account_id,id));
        CREATE OR REPLACE VIEW kb_visible_cards AS
          SELECT c.* FROM kb_authorized_cards c WHERE NOT EXISTS
          (SELECT 1 FROM kb_card_deletions d WHERE
           (d.account_id,d.card_id)=(c.account_id,c.id));
    """)


def downgrade():
    count = (
        op.get_bind()
        .execute(sa.text("SELECT count(*) FROM kb_card_deletions"))
        .scalar_one()
    )
    if count:
        raise RuntimeError("Restaure as negociações excluídas antes do downgrade")
    definition = (
        op.get_bind()
        .execute(
            sa.text("SELECT pg_get_viewdef('kb_authorized_cards'::regclass, true)")
        )
        .scalar_one()
        .rstrip("; \n")
    )
    op.execute("CREATE OR REPLACE VIEW kb_visible_cards AS " + definition)
    op.execute("DROP VIEW kb_authorized_cards; DROP TABLE kb_card_deletions")
