ALTER TABLE kb_accounts ADD COLUMN loss_reasons jsonb NOT NULL DEFAULT '["Preço", "Sem interesse", "Concorrente", "Sem retorno"]';
ALTER TABLE kb_funnels ADD COLUMN stale_days integer NOT NULL DEFAULT 7 CHECK(stale_days BETWEEN 1 AND 365);
ALTER TABLE kb_contacts ADD COLUMN inbox_id integer;
ALTER TABLE kb_cards ADD COLUMN won_at timestamptz, ADD COLUMN lost_at timestamptz,
 ADD COLUMN lost_reason text, ADD COLUMN source text, ADD COLUMN campaign text,
 ADD COLUMN temperature text, ADD COLUMN assignee_id integer, ADD COLUMN inbox_id integer;
CREATE INDEX kb_cards_created ON kb_cards(account_id,created_at);
CREATE INDEX kb_history_created ON kb_history(account_id,created_at);
CREATE TABLE kb_card_events (
 id bigserial PRIMARY KEY, account_id integer NOT NULL, card_id bigint NOT NULL,
 event_type text NOT NULL CHECK(event_type IN ('created','moved','updated','baseline')),
 stage_id bigint NOT NULL, previous_stage_id bigint, stage_kind text NOT NULL,
 stage_position numeric NOT NULL, value_cents bigint, lost_reason text,
 assignee_id integer, inbox_id integer, source text, campaign text, temperature text,
 entered_at timestamptz NOT NULL, created_at timestamptz NOT NULL DEFAULT now(),
 FOREIGN KEY(account_id,card_id) REFERENCES kb_cards(account_id,id)
);
CREATE INDEX kb_events_created ON kb_card_events(account_id,created_at);
CREATE INDEX kb_events_card ON kb_card_events(account_id,card_id,created_at,id);
UPDATE kb_cards c SET source=ct.remote_attributes->>'origem', campaign=ct.remote_attributes->>'campanha',
 temperature=ct.remote_attributes->>'temperatura',assignee_id=ct.assignee_id,inbox_id=ct.inbox_id
 FROM kb_contacts ct WHERE (ct.account_id,ct.contact_id)=(c.account_id,c.contact_id);
-- Reconstruir apenas entradas/movimentos registrados; os metadados históricos não conhecidos ficam nulos.
INSERT INTO kb_card_events(account_id,card_id,event_type,stage_id,stage_kind,stage_position,value_cents,entered_at,created_at)
SELECT c.account_id,c.id,'created',s.id,s.kind,s.position,0,c.created_at,c.created_at
FROM kb_cards c JOIN kb_stages s ON s.account_id=c.account_id AND s.id=coalesce(
 (SELECT coalesce((h.before_state->>'stage_id')::bigint,h.stage_id) FROM kb_history h
 WHERE h.account_id=c.account_id AND h.contact_id=c.contact_id AND h.funnel_id=c.funnel_id
 AND h.stage_id IS NOT NULL AND h.action IN ('contato_importado','cartao_criado','cartao_movido','movimento_externo','etapa_arquivada_movimento')
 ORDER BY h.created_at,h.id LIMIT 1), c.stage_id);
INSERT INTO kb_card_events(account_id,card_id,event_type,stage_id,previous_stage_id,stage_kind,stage_position,value_cents,entered_at,created_at)
SELECT c.account_id,c.id,CASE WHEN h.before_state->>'stage_id'=h.after_state->>'stage_id' THEN 'updated' ELSE 'moved' END,
 h.stage_id,(h.before_state->>'stage_id')::bigint,s.kind,s.position,
 coalesce((h.after_state->>'value_cents')::bigint,(h.before_state->>'value_cents')::bigint),h.created_at,h.created_at
FROM kb_history h JOIN kb_cards c ON (c.account_id,c.contact_id,c.funnel_id)=(h.account_id,h.contact_id,h.funnel_id)
JOIN kb_stages s ON (s.account_id,s.id)=(h.account_id,h.stage_id)
WHERE h.action IN ('cartao_movido','movimento_externo','etapa_arquivada_movimento');
UPDATE kb_cards c SET won_at=(SELECT max(created_at) FROM kb_card_events e WHERE e.account_id=c.account_id AND e.card_id=c.id AND e.stage_kind='won' AND e.event_type IN ('created','moved')),
 lost_at=(SELECT max(created_at) FROM kb_card_events e WHERE e.account_id=c.account_id AND e.card_id=c.id AND e.stage_kind='lost' AND e.event_type IN ('created','moved'));
INSERT INTO kb_card_events(account_id,card_id,event_type,stage_id,stage_kind,stage_position,value_cents,lost_reason,assignee_id,inbox_id,source,campaign,temperature,entered_at)
SELECT c.account_id,c.id,'baseline',c.stage_id,s.kind,s.position,c.value_cents,c.lost_reason,c.assignee_id,c.inbox_id,c.source,c.campaign,c.temperature,c.stage_entered_at
FROM kb_cards c JOIN kb_stages s ON (s.account_id,s.id)=(c.account_id,c.stage_id);
CREATE FUNCTION kb_capture_card() RETURNS trigger LANGUAGE plpgsql AS $$
DECLARE s kb_stages; previous bigint; kind text; happened timestamptz;
BEGIN
 SELECT * INTO s FROM kb_stages WHERE account_id=NEW.account_id AND id=NEW.stage_id;
 IF TG_OP='INSERT' THEN
   SELECT ct.remote_attributes->>'origem',ct.remote_attributes->>'campanha',ct.remote_attributes->>'temperatura',ct.assignee_id,ct.inbox_id
   INTO NEW.source,NEW.campaign,NEW.temperature,NEW.assignee_id,NEW.inbox_id FROM kb_contacts ct
   WHERE ct.account_id=NEW.account_id AND ct.contact_id=NEW.contact_id;
   happened:=NEW.created_at; kind:='created';
 ELSE
   IF (NEW.stage_id,NEW.value_cents,NEW.lost_reason,NEW.source,NEW.campaign,NEW.temperature,NEW.assignee_id,NEW.inbox_id)
     IS NOT DISTINCT FROM (OLD.stage_id,OLD.value_cents,OLD.lost_reason,OLD.source,OLD.campaign,OLD.temperature,OLD.assignee_id,OLD.inbox_id) THEN RETURN NEW; END IF;
   previous:=OLD.stage_id; happened:=now();
   kind:=CASE WHEN NEW.stage_id<>OLD.stage_id THEN 'moved' ELSE 'updated' END;
 END IF;
 IF kind IN ('created','moved') THEN
   NEW.stage_entered_at:=happened;
   IF s.kind='won' THEN NEW.won_at:=happened; END IF;
   IF s.kind='lost' THEN NEW.lost_at:=happened; ELSE NEW.lost_reason:=NULL; END IF;
 END IF;
 RETURN NEW;
END $$;
CREATE FUNCTION kb_log_card() RETURNS trigger LANGUAGE plpgsql AS $$
DECLARE s kb_stages; previous bigint; kind text; happened timestamptz;
BEGIN
 SELECT * INTO s FROM kb_stages WHERE account_id=NEW.account_id AND id=NEW.stage_id;
 IF TG_OP='INSERT' THEN kind:='created'; happened:=NEW.created_at;
 ELSE
   IF (NEW.stage_id,NEW.value_cents,NEW.lost_reason,NEW.source,NEW.campaign,NEW.temperature,NEW.assignee_id,NEW.inbox_id)
     IS NOT DISTINCT FROM (OLD.stage_id,OLD.value_cents,OLD.lost_reason,OLD.source,OLD.campaign,OLD.temperature,OLD.assignee_id,OLD.inbox_id) THEN RETURN NEW; END IF;
   previous:=OLD.stage_id; happened:=now(); kind:=CASE WHEN NEW.stage_id<>OLD.stage_id THEN 'moved' ELSE 'updated' END;
 END IF;
 INSERT INTO kb_card_events(account_id,card_id,event_type,stage_id,previous_stage_id,stage_kind,stage_position,value_cents,lost_reason,assignee_id,inbox_id,source,campaign,temperature,entered_at,created_at)
 VALUES(NEW.account_id,NEW.id,kind,NEW.stage_id,previous,s.kind,s.position,NEW.value_cents,NEW.lost_reason,NEW.assignee_id,NEW.inbox_id,NEW.source,NEW.campaign,NEW.temperature,NEW.stage_entered_at,happened);
 RETURN NEW;
END $$;
CREATE TRIGGER kb_card_capture BEFORE INSERT OR UPDATE ON kb_cards FOR EACH ROW EXECUTE FUNCTION kb_capture_card();
CREATE TRIGGER kb_card_log AFTER INSERT OR UPDATE ON kb_cards FOR EACH ROW EXECUTE FUNCTION kb_log_card();
CREATE FUNCTION kb_contact_dimensions() RETURNS trigger LANGUAGE plpgsql AS $$
BEGIN
 UPDATE kb_cards SET source=NEW.remote_attributes->>'origem',campaign=NEW.remote_attributes->>'campanha',temperature=NEW.remote_attributes->>'temperatura',
 assignee_id=NEW.assignee_id,inbox_id=NEW.inbox_id WHERE account_id=NEW.account_id AND contact_id=NEW.contact_id;
 RETURN NEW;
END $$;
CREATE TRIGGER kb_contact_dimensions AFTER UPDATE OF remote_attributes,assignee_id,inbox_id ON kb_contacts FOR EACH ROW EXECUTE FUNCTION kb_contact_dimensions();
CREATE TABLE kb_metrics_cache(account_id integer NOT NULL REFERENCES kb_accounts(account_id), cache_key text NOT NULL, payload jsonb NOT NULL, fetched_at timestamptz NOT NULL DEFAULT now(), PRIMARY KEY(account_id,cache_key));
