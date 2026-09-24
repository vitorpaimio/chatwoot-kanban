"""Provisionamento, importação retomável e recuperação por conta."""

from pathlib import Path

from alembic import op

revision = "009"
down_revision = "008"


def upgrade():
    op.get_bind().exec_driver_sql(
        (Path(__file__).parents[1] / "phase2.sql").read_text()
    )


def downgrade():
    raise RuntimeError("Preserve o manifesto e os checkpoints; restaure o backup.")
