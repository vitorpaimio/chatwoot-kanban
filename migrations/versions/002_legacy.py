"""Rastreabilidade de importações legadas, sem modificar as tabelas originais."""

from alembic import op

revision = "002"
down_revision = "001"


def upgrade():
    op.execute("""CREATE TABLE kb_legacy_imports (
        source_table text NOT NULL, source_id bigint NOT NULL,
        account_id integer NOT NULL REFERENCES kb_accounts(account_id),
        target_id bigint NOT NULL, imported_at timestamptz NOT NULL DEFAULT now(),
        PRIMARY KEY(source_table,source_id)
    )""")


def downgrade():
    raise RuntimeError(
        "Restaure o backup; reversão destrutiva automática desabilitada."
    )
