-- Transferência entre funis: o destino é um cartão novo ligado à origem.
ALTER TABLE kb_cards ADD COLUMN origin_card_id bigint,
 ADD COLUMN transferred_at timestamptz;
ALTER TABLE kb_cards ADD CONSTRAINT kb_cards_origin_fkey
 FOREIGN KEY(account_id,origin_card_id) REFERENCES kb_cards(account_id,id);
CREATE INDEX kb_cards_origin ON kb_cards(account_id,origin_card_id)
 WHERE origin_card_id IS NOT NULL;
ALTER TABLE kb_card_events DROP CONSTRAINT kb_card_events_event_type_check,
 ADD CONSTRAINT kb_card_events_event_type_check
 CHECK(event_type IN ('created','moved','updated','baseline','transferred'));
-- Origem encerrada por transferência: o último evento leva o tipo 'transferred',
-- que não é aberto, ganho nem perdido nas métricas.
CREATE OR REPLACE FUNCTION kb_log_card() RETURNS trigger LANGUAGE plpgsql AS $$
DECLARE s kb_stages; previous bigint; kind text; happened timestamptz;
BEGIN
 SELECT * INTO s FROM kb_stages WHERE account_id=NEW.account_id AND id=NEW.stage_id;
 IF TG_OP='INSERT' THEN kind:='created'; happened:=NEW.created_at;
 ELSE
   IF (NEW.stage_id,NEW.value_cents,NEW.lost_reason,NEW.source,NEW.campaign,NEW.temperature,NEW.assignee_id,NEW.inbox_id,NEW.transferred_at)
     IS NOT DISTINCT FROM (OLD.stage_id,OLD.value_cents,OLD.lost_reason,OLD.source,OLD.campaign,OLD.temperature,OLD.assignee_id,OLD.inbox_id,OLD.transferred_at) THEN RETURN NEW; END IF;
   previous:=OLD.stage_id; happened:=kb_occurred_at();
   kind:=CASE WHEN NEW.stage_id<>OLD.stage_id THEN 'moved'
     WHEN OLD.transferred_at IS NULL AND NEW.transferred_at IS NOT NULL THEN 'transferred'
     ELSE 'updated' END;
 END IF;
 INSERT INTO kb_card_events(account_id,card_id,event_type,stage_id,previous_stage_id,stage_kind,stage_position,value_cents,lost_reason,assignee_id,inbox_id,source,campaign,temperature,entered_at,created_at)
 VALUES(NEW.account_id,NEW.id,kind,NEW.stage_id,previous,
  CASE WHEN NEW.transferred_at IS NOT NULL THEN 'transferred' ELSE s.kind END,
  s.position,NEW.value_cents,NEW.lost_reason,NEW.assignee_id,NEW.inbox_id,NEW.source,NEW.campaign,NEW.temperature,NEW.stage_entered_at,happened);
 RETURN NEW;
END $$;
CREATE OR REPLACE FUNCTION kb_stage_metric_snapshot() RETURNS trigger LANGUAGE plpgsql AS $$
BEGIN
  IF (NEW.kind,NEW.position) IS NOT DISTINCT FROM (OLD.kind,OLD.position)
  THEN RETURN NEW; END IF;
  INSERT INTO kb_card_events(account_id,card_id,event_type,stage_id,
    stage_kind,stage_position,value_cents,lost_reason,assignee_id,inbox_id,
    source,campaign,temperature,entered_at)
  SELECT c.account_id,c.id,'updated',c.stage_id,
    CASE WHEN c.transferred_at IS NOT NULL THEN 'transferred' ELSE NEW.kind END,
    NEW.position,c.value_cents,c.lost_reason,c.assignee_id,c.inbox_id,c.source,
    c.campaign,c.temperature,c.stage_entered_at
  FROM kb_cards c WHERE c.account_id=NEW.account_id AND c.stage_id=NEW.id;
  RETURN NEW;
END $$;
