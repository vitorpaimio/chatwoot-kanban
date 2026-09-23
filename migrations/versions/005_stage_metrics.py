"""Registra a classificação atual das etapas sem inventar movimentos."""

from alembic import op

revision = "005"
down_revision = "004"


def upgrade():
    op.execute("""
    CREATE FUNCTION kb_stage_metric_snapshot() RETURNS trigger LANGUAGE plpgsql AS $$
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
    CREATE TRIGGER kb_stage_metric_snapshot AFTER UPDATE OF kind,position
    ON kb_stages FOR EACH ROW EXECUTE FUNCTION kb_stage_metric_snapshot();
    """)


def downgrade():
    op.execute("DROP TRIGGER kb_stage_metric_snapshot ON kb_stages")
    op.execute("DROP FUNCTION kb_stage_metric_snapshot()")
