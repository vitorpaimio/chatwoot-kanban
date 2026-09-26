"""Data real de movimentos, primeiro contato e valor atual nas métricas."""

from pathlib import Path

from alembic import op

revision = "014"
down_revision = "013"
ROOT = Path(__file__).parents[1]


def function(path: str, start: str, end: str) -> str:
    """Recorta a definição anterior de uma função para o downgrade."""
    text = (ROOT / path).read_text()
    body = text[text.index(start) : text.index(end)].strip()
    return body.replace("CREATE FUNCTION", "CREATE OR REPLACE FUNCTION", 1)


def upgrade():
    op.execute((ROOT / "occurred_at.sql").read_text())


def downgrade():
    op.execute(
        function(
            "phase2.sql",
            "CREATE OR REPLACE FUNCTION kb_capture_card()",
            "CREATE OR REPLACE FUNCTION kb_contact_dimensions()",
        )
    )
    op.execute(
        function(
            "metrics.sql",
            "CREATE FUNCTION kb_log_card()",
            "CREATE TRIGGER kb_card_capture",
        )
    )
    op.execute("DROP FUNCTION kb_occurred_at()")
    op.execute("ALTER TABLE kb_contacts DROP COLUMN first_seen_at")
