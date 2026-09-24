"""Checkpoint distingue contato importado de recurso remoto ausente."""

from alembic import op

revision = "011"
down_revision = "010"


def upgrade():
    op.execute(
        "ALTER TABLE kb_import_seen ADD COLUMN imported boolean NOT NULL DEFAULT true"
    )


def downgrade():
    op.execute("ALTER TABLE kb_import_seen DROP COLUMN imported")
