-- Origem pelo anúncio (Click-to-WhatsApp): vale quando o atributo mapeado está vazio.
ALTER TABLE kb_contacts ADD COLUMN ad_source text, ADD COLUMN ad_campaign text,
 ADD COLUMN ad_id text, ADD COLUMN ad_click_id text, ADD COLUMN ad_seen_at timestamptz;
CREATE OR REPLACE FUNCTION kb_capture_card() RETURNS trigger LANGUAGE plpgsql AS $$
DECLARE s kb_stages; previous bigint; kind text; happened timestamptz;
BEGIN
 SELECT * INTO s FROM kb_stages WHERE account_id=NEW.account_id AND id=NEW.stage_id;
 IF TG_OP='INSERT' THEN
   SELECT coalesce(kb_attribute_value(NEW.account_id,ct.remote_attributes,'origem'),ct.ad_source),coalesce(kb_attribute_value(NEW.account_id,ct.remote_attributes,'campanha'),ct.ad_campaign),kb_attribute_value(NEW.account_id,ct.remote_attributes,'temperatura'),ct.assignee_id,ct.inbox_id
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
CREATE OR REPLACE FUNCTION kb_contact_dimensions() RETURNS trigger LANGUAGE plpgsql AS $$
BEGIN
 UPDATE kb_cards SET source=coalesce(kb_attribute_value(NEW.account_id,NEW.remote_attributes,'origem'),NEW.ad_source),campaign=coalesce(kb_attribute_value(NEW.account_id,NEW.remote_attributes,'campanha'),NEW.ad_campaign),temperature=kb_attribute_value(NEW.account_id,NEW.remote_attributes,'temperatura'),
 assignee_id=NEW.assignee_id,inbox_id=NEW.inbox_id WHERE account_id=NEW.account_id AND contact_id=NEW.contact_id;
 RETURN NEW;
END $$;
DROP TRIGGER kb_contact_dimensions ON kb_contacts;
CREATE TRIGGER kb_contact_dimensions AFTER UPDATE OF remote_attributes,assignee_id,inbox_id,ad_source,ad_campaign
 ON kb_contacts FOR EACH ROW EXECUTE FUNCTION kb_contact_dimensions();
