"""Origem e campanha preenchidas pelo anúncio de Click-to-WhatsApp."""

from pathlib import Path

from alembic import op

revision = "015"
down_revision = "014"
ROOT = Path(__file__).parents[1]


def function(path: str, start: str, end: str) -> str:
    """Recorta a definição anterior de uma função para o downgrade."""
    text = (ROOT / path).read_text()
    return text[text.index(start) : text.index(end, text.index(start))].strip()


def upgrade():
    op.execute((ROOT / "ad_origin.sql").read_text())


def downgrade():
    op.execute(
        function(
            "occurred_at.sql",
            "CREATE OR REPLACE FUNCTION kb_capture_card()",
            "CREATE OR REPLACE FUNCTION kb_log_card()",
        )
    )
    op.execute(
        function(
            "phase2.sql",
            "CREATE OR REPLACE FUNCTION kb_contact_dimensions()",
            "END $$;",
        )
        + "\nEND $$;"
    )
    op.execute("""
        DROP TRIGGER kb_contact_dimensions ON kb_contacts;
        CREATE TRIGGER kb_contact_dimensions AFTER UPDATE OF
          remote_attributes,assignee_id,inbox_id ON kb_contacts FOR EACH ROW
          EXECUTE FUNCTION kb_contact_dimensions();
        ALTER TABLE kb_contacts DROP COLUMN ad_source, DROP COLUMN ad_campaign,
          DROP COLUMN ad_id, DROP COLUMN ad_click_id, DROP COLUMN ad_seen_at;
    """)
