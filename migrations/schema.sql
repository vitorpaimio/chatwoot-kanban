CREATE TABLE kb_accounts (
 account_id integer PRIMARY KEY, token_cipher text NOT NULL,
 webhook_cipher text, webhook_id integer, app_id integer,
 activation_status text NOT NULL DEFAULT 'pending', activation_error text,
 imported_count integer NOT NULL DEFAULT 0, timezone text NOT NULL DEFAULT 'America/Sao_Paulo',
 updated_at timestamptz NOT NULL DEFAULT now()
);
CREATE TABLE kb_agents (
 account_id integer NOT NULL REFERENCES kb_accounts(account_id), user_id integer NOT NULL,
 name text NOT NULL, role text NOT NULL, PRIMARY KEY(account_id,user_id)
);
CREATE TABLE kb_funnels (
 id bigserial PRIMARY KEY, account_id integer NOT NULL REFERENCES kb_accounts(account_id),
 name text NOT NULL CHECK(length(name)>0), position numeric NOT NULL DEFAULT 1024,
 is_primary boolean NOT NULL DEFAULT false, archived boolean NOT NULL DEFAULT false,
 UNIQUE(account_id,id)
);
CREATE UNIQUE INDEX kb_primary_funnel ON kb_funnels(account_id) WHERE is_primary;
CREATE TABLE kb_stages (
 id bigserial PRIMARY KEY, account_id integer NOT NULL, funnel_id bigint NOT NULL,
 name text NOT NULL CHECK(length(name)>0), color text NOT NULL DEFAULT '#6366f1',
 kind text NOT NULL DEFAULT 'open' CHECK(kind IN ('open','won','lost')),
 position numeric NOT NULL DEFAULT 1024, archived boolean NOT NULL DEFAULT false,
 UNIQUE(account_id,funnel_id,id), UNIQUE(account_id,id),
 FOREIGN KEY(account_id,funnel_id) REFERENCES kb_funnels(account_id,id)
);
CREATE TABLE kb_contacts (
 account_id integer NOT NULL REFERENCES kb_accounts(account_id), contact_id integer NOT NULL,
 name text NOT NULL, phone text, email text, thumbnail text,
 labels jsonb NOT NULL DEFAULT '[]', assignee_id integer, assignee_name text,
 conversation_id integer, last_activity_at timestamptz,
 last_card_id bigint, remote_attributes jsonb NOT NULL DEFAULT '{}',
 PRIMARY KEY(account_id,contact_id)
);
CREATE TABLE kb_cards (
 id bigserial PRIMARY KEY, account_id integer NOT NULL, contact_id integer NOT NULL,
 funnel_id bigint NOT NULL, stage_id bigint NOT NULL,
 position numeric NOT NULL DEFAULT 1024, version integer NOT NULL DEFAULT 1,
 value_cents bigint NOT NULL DEFAULT 0 CHECK(value_cents>=0),
 stage_entered_at timestamptz NOT NULL DEFAULT now(), created_at timestamptz NOT NULL DEFAULT now(),
 UNIQUE(account_id,funnel_id,contact_id), UNIQUE(account_id,id),
 FOREIGN KEY(account_id,contact_id) REFERENCES kb_contacts(account_id,contact_id),
 FOREIGN KEY(account_id,funnel_id,stage_id) REFERENCES kb_stages(account_id,funnel_id,id)
);
CREATE INDEX kb_cards_board ON kb_cards(account_id,funnel_id,stage_id,position);
CREATE TABLE kb_tasks (
 id bigserial PRIMARY KEY, account_id integer NOT NULL, contact_id integer NOT NULL,
 message text NOT NULL, due_date date NOT NULL, status text NOT NULL DEFAULT 'active'
 CHECK(status IN ('active','closed')), created_by integer, closed_by integer,
 version integer NOT NULL DEFAULT 1, created_at timestamptz NOT NULL DEFAULT now(),
 closed_at timestamptz, due_state text NOT NULL DEFAULT 'active',
 FOREIGN KEY(account_id,contact_id) REFERENCES kb_contacts(account_id,contact_id),
 FOREIGN KEY(account_id,created_by) REFERENCES kb_agents(account_id,user_id),
 FOREIGN KEY(account_id,closed_by) REFERENCES kb_agents(account_id,user_id)
);
CREATE UNIQUE INDEX kb_active_task ON kb_tasks(account_id,contact_id) WHERE status='active';
CREATE TABLE kb_sync (
 account_id integer NOT NULL, contact_id integer NOT NULL, version integer NOT NULL DEFAULT 1,
 synced_version integer NOT NULL DEFAULT 0, status text NOT NULL DEFAULT 'pending',
 attempts integer NOT NULL DEFAULT 0, next_attempt timestamptz NOT NULL DEFAULT now(),
 last_error text, projection jsonb, updated_at timestamptz NOT NULL DEFAULT now(),
 PRIMARY KEY(account_id,contact_id),
 FOREIGN KEY(account_id,contact_id) REFERENCES kb_contacts(account_id,contact_id)
);
CREATE TABLE kb_history (
 id bigserial PRIMARY KEY, account_id integer NOT NULL REFERENCES kb_accounts(account_id),
 contact_id integer, actor_id integer, actor_name text NOT NULL,
 action text NOT NULL, before_state jsonb, after_state jsonb, funnel_id bigint, stage_id bigint,
 created_at timestamptz NOT NULL DEFAULT now()
);
CREATE INDEX kb_history_account ON kb_history(account_id,contact_id,id DESC);
CREATE TABLE kb_deliveries (
 id bigserial PRIMARY KEY, account_id integer NOT NULL REFERENCES kb_accounts(account_id),
 delivery_id text NOT NULL, event_type text NOT NULL, contact_id integer,
 payload jsonb NOT NULL, status text NOT NULL DEFAULT 'received',
 attempts integer NOT NULL DEFAULT 0, next_attempt timestamptz NOT NULL DEFAULT now(),
 error text, received_at timestamptz NOT NULL DEFAULT now(), processed_at timestamptz,
 UNIQUE(account_id,delivery_id)
);
CREATE INDEX kb_deliveries_pending ON kb_deliveries(next_attempt) WHERE status<>'processed';
