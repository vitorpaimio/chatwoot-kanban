"""Eventos temporais e dimensões para métricas, preservando cartões e histórico."""

from pathlib import Path

from alembic import op

revision = "004"
down_revision = "003"


def upgrade():
    op.get_bind().exec_driver_sql(
        (Path(__file__).parents[1] / "metrics.sql").read_text()
    )


def downgrade():
    raise RuntimeError(
        "Reverta o aplicativo mantendo as colunas aditivas; restaure "
        "o backup para remover eventos."
    )
