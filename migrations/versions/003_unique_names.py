"""Nomes de etapas inequívocos dentro de cada funil ativo."""

from alembic import op

revision = "003"
down_revision = "002"


def upgrade():
    op.execute("""CREATE UNIQUE INDEX kb_stage_name
        ON kb_stages(account_id,funnel_id,lower(name)) WHERE NOT archived""")


def downgrade():
    op.execute("DROP INDEX kb_stage_name")
