ALTER TABLE kb_accounts
 ADD COLUMN attribute_mappings jsonb NOT NULL DEFAULT '{"origem":"origem","campanha":"campanha","temperatura":"temperatura"}',
 ADD COLUMN provisioning_warnings jsonb NOT NULL DEFAULT '[]',
 ADD COLUMN activation_attempts integer NOT NULL DEFAULT 0,
 ADD COLUMN activation_next_attempt timestamptz NOT NULL DEFAULT now(),
 ADD COLUMN import_status text NOT NULL DEFAULT 'idle',
 ADD COLUMN import_mode text NOT NULL DEFAULT 'metadata' CHECK(import_mode IN ('metadata','cards')),
 ADD COLUMN import_page integer NOT NULL DEFAULT 1,
 ADD COLUMN import_pending jsonb NOT NULL DEFAULT '[]',
 ADD COLUMN import_estimate integer,
 ADD COLUMN import_error text,
 ADD COLUMN import_attempts integer NOT NULL DEFAULT 0,
 ADD COLUMN import_next_attempt timestamptz NOT NULL DEFAULT now(),
 ADD COLUMN import_actor jsonb,
 ADD COLUMN import_funnel_id bigint,
 ADD COLUMN import_stage_id bigint,
 ADD COLUMN reconcile_cursor integer NOT NULL DEFAULT 0,
 ADD COLUMN reconcile_next_attempt timestamptz NOT NULL DEFAULT now()+interval '5 minutes',
 ADD COLUMN reconcile_error text,
 ADD COLUMN reconcile_attempts integer NOT NULL DEFAULT 0,
 ADD COLUMN processing_limit integer NOT NULL DEFAULT 10 CHECK(processing_limit BETWEEN 1 AND 100);
CREATE TABLE kb_resources (
 account_id integer NOT NULL REFERENCES kb_accounts(account_id),
 resource_type text NOT NULL, resource_key text NOT NULL,
 remote_id bigint NOT NULL, ownership text NOT NULL CHECK(ownership IN ('created','preexisting')),
 definition jsonb NOT NULL, updated_at timestamptz NOT NULL DEFAULT now(),
 PRIMARY KEY(account_id,resource_type,resource_key)
);
CREATE TABLE kb_import_seen (
 account_id integer NOT NULL REFERENCES kb_accounts(account_id), contact_id integer NOT NULL,
 PRIMARY KEY(account_id,contact_id)
);
CREATE TABLE kb_worker_heartbeat (
 worker_id text PRIMARY KEY, seen_at timestamptz NOT NULL DEFAULT now()
);
CREATE FUNCTION kb_attribute_value(account integer, attrs jsonb, dimension text)
RETURNS text LANGUAGE sql STABLE AS $$
 SELECT attrs->>(attribute_mappings->>dimension) FROM kb_accounts WHERE account_id=account
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
CREATE OR REPLACE FUNCTION kb_contact_dimensions() RETURNS trigger LANGUAGE plpgsql AS $$
BEGIN
 UPDATE kb_cards SET source=kb_attribute_value(NEW.account_id,NEW.remote_attributes,'origem'),campaign=kb_attribute_value(NEW.account_id,NEW.remote_attributes,'campanha'),temperature=kb_attribute_value(NEW.account_id,NEW.remote_attributes,'temperatura'),
 assignee_id=NEW.assignee_id,inbox_id=NEW.inbox_id WHERE account_id=NEW.account_id AND contact_id=NEW.contact_id;
 RETURN NEW;
END $$;
