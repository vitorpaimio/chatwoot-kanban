"""Transferência de negociações entre funis com vínculo à origem."""

from pathlib import Path

import sqlalchemy as sa
from alembic import op

revision = "016"
down_revision = "015"
ROOT = Path(__file__).parents[1]
COLUMNS = ",\n    origin_card_id,\n    transferred_at"
# As views guardam a lista de colunas da criação; ordem de dependência.
VIEWS = ("kb_authorized_cards", "kb_visible_cards", "kb_visible_history")


def definition(view: str) -> str:
    return (
        op.get_bind()
        .execute(sa.text(f"SELECT pg_get_viewdef('{view}'::regclass, true)"))
        .scalar_one()
        .rstrip("; \n")
    )


def upgrade():
    op.execute((ROOT / "transfer.sql").read_text())
    for view, source in (
        ("kb_authorized_cards", "kb_cards"),
        ("kb_visible_cards", "kb_authorized_cards"),
    ):
        text = definition(view)
        marker = f"\n   FROM {source} c"
        assert text.count(marker) == 1, view
        op.execute(
            f"CREATE OR REPLACE VIEW {view} AS "
            + text.replace(marker, COLUMNS + marker)
        )


def downgrade():
    count = (
        op.get_bind()
        .execute(
            sa.text(
                "SELECT count(*) FROM kb_cards WHERE origin_card_id IS NOT NULL "
                "OR transferred_at IS NOT NULL"
            )
        )
        .scalar_one()
    )
    if count:
        raise RuntimeError("Há negociações transferidas; o downgrade perde o vínculo")
    views = {view: definition(view).replace(COLUMNS, "") for view in VIEWS}
    op.execute("DROP VIEW " + ", ".join(reversed(VIEWS)))
    for view in VIEWS:
        op.execute(f"CREATE VIEW {view} AS {views[view]}")
    text = (ROOT / "occurred_at.sql").read_text()
    start = text.index("CREATE OR REPLACE FUNCTION kb_log_card()")
    op.execute(text[start : text.index("END $$;", start) + len("END $$;")])
    op.execute("""
    CREATE OR REPLACE FUNCTION kb_stage_metric_snapshot() RETURNS trigger
    LANGUAGE plpgsql AS $$
    BEGIN
      IF (NEW.kind,NEW.position) IS NOT DISTINCT FROM (OLD.kind,OLD.position)
      THEN RETURN NEW; END IF;
      INSERT INTO kb_card_events(account_id,card_id,event_type,stage_id,
        stage_kind,stage_position,value_cents,lost_reason,assignee_id,inbox_id,
        source,campaign,temperature,entered_at)
      SELECT c.account_id,c.id,'updated',c.stage_id,NEW.kind,NEW.position,
        c.value_cents,c.lost_reason,c.assignee_id,c.inbox_id,c.source,c.campaign,
        c.temperature,c.stage_entered_at
      FROM kb_cards c WHERE c.account_id=NEW.account_id AND c.stage_id=NEW.id;
      RETURN NEW;
    END $$;
    ALTER TABLE kb_card_events DROP CONSTRAINT kb_card_events_event_type_check,
      ADD CONSTRAINT kb_card_events_event_type_check
      CHECK(event_type IN ('created','moved','updated','baseline'));
    DROP INDEX kb_cards_origin;
    ALTER TABLE kb_cards DROP CONSTRAINT kb_cards_origin_fkey,
      DROP COLUMN origin_card_id, DROP COLUMN transferred_at;
    """)
