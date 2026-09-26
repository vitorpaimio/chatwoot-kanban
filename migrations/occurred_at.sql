-- Data real de movimentos: os gatilhos usam kanban.occurred_at quando definido.
ALTER TABLE kb_contacts ADD COLUMN first_seen_at timestamptz;
CREATE FUNCTION kb_occurred_at() RETURNS timestamptz LANGUAGE sql STABLE AS $$
 SELECT coalesce(nullif(current_setting('kanban.occurred_at',true),'')::timestamptz,now())
$$;
CREATE OR REPLACE FUNCTION kb_capture_card() RETURNS trigger LANGUAGE plpgsql AS $$
DECLARE s kb_stages; previous bigint; kind text; happened timestamptz;
BEGIN
 SELECT * INTO s FROM kb_stages WHERE account_id=NEW.account_id AND id=NEW.stage_id;
 IF TG_OP='INSERT' THEN
   SELECT kb_attribute_value(NEW.account_id,ct.remote_attributes,'origem'),kb_attribute_value(NEW.account_id,ct.remote_attributes,'campanha'),kb_attribute_value(NEW.account_id,ct.remote_attributes,'temperatura'),ct.assignee_id,ct.inbox_id
   INTO NEW.source,NEW.campaign,NEW.temperature,NEW.assignee_id,NEW.inbox_id FROM kb_contacts ct
   WHERE ct.account_id=NEW.account_id AND ct.contact_id=NEW.contact_id;
   happened:=NEW.created_at; kind:='created';
 ELSE
   IF (NEW.stage_id,NEW.value_cents,NEW.lost_reason,NEW.source,NEW.campaign,NEW.temperature,NEW.assignee_id,NEW.inbox_id)
     IS NOT DISTINCT FROM (OLD.stage_id,OLD.value_cents,OLD.lost_reason,OLD.source,OLD.campaign,OLD.temperature,OLD.assignee_id,OLD.inbox_id) THEN RETURN NEW; END IF;
   previous:=OLD.stage_id; happened:=kb_occurred_at();
   kind:=CASE WHEN NEW.stage_id<>OLD.stage_id THEN 'moved' ELSE 'updated' END;
 END IF;
 IF kind IN ('created','moved') THEN
   NEW.stage_entered_at:=happened;
   IF s.kind='won' THEN NEW.won_at:=happened; END IF;
   IF s.kind='lost' THEN NEW.lost_at:=happened; ELSE NEW.lost_reason:=NULL; END IF;
 END IF;
 RETURN NEW;
END $$;
CREATE OR REPLACE FUNCTION kb_log_card() RETURNS trigger LANGUAGE plpgsql AS $$
DECLARE s kb_stages; previous bigint; kind text; happened timestamptz;
BEGIN
 SELECT * INTO s FROM kb_stages WHERE account_id=NEW.account_id AND id=NEW.stage_id;
 IF TG_OP='INSERT' THEN kind:='created'; happened:=NEW.created_at;
 ELSE
   IF (NEW.stage_id,NEW.value_cents,NEW.lost_reason,NEW.source,NEW.campaign,NEW.temperature,NEW.assignee_id,NEW.inbox_id)
     IS NOT DISTINCT FROM (OLD.stage_id,OLD.value_cents,OLD.lost_reason,OLD.source,OLD.campaign,OLD.temperature,OLD.assignee_id,OLD.inbox_id) THEN RETURN NEW; END IF;
   previous:=OLD.stage_id; happened:=kb_occurred_at(); kind:=CASE WHEN NEW.stage_id<>OLD.stage_id THEN 'moved' ELSE 'updated' END;
 END IF;
 INSERT INTO kb_card_events(account_id,card_id,event_type,stage_id,previous_stage_id,stage_kind,stage_position,value_cents,lost_reason,assignee_id,inbox_id,source,campaign,temperature,entered_at,created_at)
 VALUES(NEW.account_id,NEW.id,kind,NEW.stage_id,previous,s.kind,s.position,NEW.value_cents,NEW.lost_reason,NEW.assignee_id,NEW.inbox_id,NEW.source,NEW.campaign,NEW.temperature,NEW.stage_entered_at,happened);
 RETURN NEW;
END $$;
