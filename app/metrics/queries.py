"""Agregações temporais no PostgreSQL; limites de data são semiabertos."""

BASE = """
WITH snapshot AS (
 SELECT DISTINCT ON (e.card_id) e.* FROM kb_card_events e
 WHERE e.account_id=$1 AND e.created_at<$3 AND e.created_at<=now()
 ORDER BY e.card_id,e.created_at DESC,e.id DESC
), cards AS (
 SELECT c.id,c.contact_id,c.funnel_id,c.created_at,s.stage_id,s.stage_kind,
 s.value_cents,
 s.assignee_id,s.inbox_id,s.source,s.campaign,s.temperature,f.stale_days,ct.name,
 coalesce(a.name,ct.assignee_name,'Não atribuído') AS assignee_name
 FROM kb_cards c JOIN snapshot s ON s.card_id=c.id
 JOIN kb_funnels f ON (f.account_id,f.id)=(c.account_id,c.funnel_id)
 JOIN kb_contacts ct ON (ct.account_id,ct.contact_id)=(c.account_id,c.contact_id)
 LEFT JOIN kb_agents a ON a.account_id=c.account_id AND a.user_id=s.assignee_id
 WHERE c.account_id=$1 AND ($4::bigint IS NULL OR c.funnel_id=$4)
 AND ($5::integer IS NULL OR s.assignee_id=$5)
 AND ($6::integer IS NULL OR s.inbox_id=$6)
), events AS (
 SELECT e.* FROM kb_card_events e JOIN cards c ON c.id=e.card_id
 WHERE e.account_id=$1 AND e.created_at<$3 AND e.created_at<=now()
), entries AS (
 SELECT * FROM events WHERE event_type IN ('created','moved')
), wins AS (
 SELECT DISTINCT ON(card_id) * FROM entries WHERE stage_kind='won' AND created_at >=$2
 ORDER BY card_id,created_at,id
), losses AS (
 SELECT DISTINCT ON(card_id) * FROM entries WHERE stage_kind='lost' AND created_at
 >=$2
 ORDER BY card_id,created_at,id
), task_scope AS (
 SELECT t.* FROM kb_tasks t WHERE t.account_id=$1 AND t.created_at<$3
 AND EXISTS(SELECT 1 FROM cards c WHERE c.contact_id=t.contact_id)
)
"""
SUMMARY = (
    BASE
    + """
SELECT
 (SELECT count(*) FROM cards WHERE created_at >=$2) AS leads,
 (SELECT count(*) FROM cards WHERE stage_kind='open') AS ongoing,
 (SELECT count(*) FROM wins) AS wins,
 (SELECT coalesce(sum(value_cents),0) FROM wins) AS revenue,
 (SELECT count(*) FROM losses) AS losses,
 (SELECT coalesce(100.0*count(*)/nullif(count(*)+(SELECT count(*) FROM losses),0),
 0) FROM wins) AS win_rate,
 (SELECT avg(value_cents) FROM wins) AS average_ticket,
 (SELECT coalesce(sum(value_cents),0) FROM cards WHERE stage_kind='open') AS
 open_value,
 (SELECT avg(extract(epoch FROM (w.created_at-c.created_at))/86400) FROM wins w
 JOIN cards c ON c.id=w.card_id) AS cycle_days
"""
)
TASKS = (
    BASE
    + """
SELECT count(*) FILTER(WHERE closed_at IS NULL OR closed_at >=$3) AS open,
 count(*) FILTER(WHERE (closed_at IS NULL OR closed_at >=$3) AND due_date <
 (least($3-interval '1 microsecond',now())
 AT TIME ZONE 'America/Sao_Paulo')::date) AS overdue,
 count(*) FILTER(WHERE closed_at >=$2 AND closed_at<$3) AS completed,
 coalesce(100.0*count(*) FILTER(WHERE closed_at >=$2 AND closed_at<$3 AND
 (closed_at AT TIME ZONE 'America/Sao_Paulo')::date<=due_date)/nullif(count(*)
 FILTER(WHERE closed_at >=$2 AND closed_at<$3),0),0) AS on_time_rate
FROM task_scope
"""
)
FUNNEL = (
    BASE
    + """
, cohorts AS (
 SELECT DISTINCT ON(card_id,stage_id) * FROM entries WHERE created_at >=$2
 ORDER BY card_id,stage_id,created_at,id
), spans AS (
 SELECT e.*,lead(created_at) OVER(PARTITION BY card_id ORDER BY created_at,id) AS
 exited_at FROM entries e
)
SELECT s.id,s.funnel_id,f.name AS funnel,s.name,s.position,
 count(co.card_id) AS quantity,coalesce(sum(co.value_cents),0) AS value,
 coalesce(100.0*count(co.card_id) FILTER(WHERE EXISTS(
 SELECT 1 FROM kb_card_events later WHERE later.account_id=$1 AND
 later.card_id=co.card_id
 AND later.event_type IN ('created','moved') AND (later.created_at,
 later.id)>(co.created_at,co.id)
 AND later.created_at<=now() AND
 later.stage_position>co.stage_position))/nullif(count(co.card_id),0),0) AS
 conversion,
 coalesce(100.0*count(co.card_id) FILTER(WHERE EXISTS(
 SELECT 1 FROM kb_card_events later WHERE later.account_id=$1 AND
 later.card_id=co.card_id
 AND later.event_type IN ('created','moved') AND (later.created_at,
 later.id)>(co.created_at,co.id)
 AND later.created_at<=now() AND later.stage_id=(SELECT ns.id FROM kb_stages ns
 WHERE ns.account_id=$1 AND ns.funnel_id=s.funnel_id AND ns.position>s.position
 ORDER BY ns.position,ns.id LIMIT 1)
 ))/nullif(count(co.card_id),0),0) AS next_conversion,
 (SELECT avg(extract(epoch FROM (sp.exited_at-sp.created_at))/86400) FROM spans sp
 WHERE sp.stage_id=s.id AND sp.exited_at >=$2 AND sp.exited_at<$3) AS dwell_days
FROM kb_stages s JOIN kb_funnels f ON (f.account_id,f.id)=(s.account_id,s.funnel_id)
LEFT JOIN cohorts co ON co.stage_id=s.id
WHERE s.account_id=$1 AND ($4::bigint IS NULL OR s.funnel_id=$4)
GROUP BY s.id,f.name ORDER BY s.funnel_id,s.position,s.id
"""
)
STALE = (
    BASE
    + """
, activity AS (
SELECT c.*,greatest(c.created_at,
 (SELECT max(e.created_at) FROM entries e WHERE e.card_id=c.id),
 (SELECT max(t.closed_at) FROM task_scope t WHERE t.contact_id=c.contact_id AND
 t.closed_at<$3)
 ) AS last_activity FROM cards c WHERE c.stage_kind='open'
)
SELECT id,contact_id,funnel_id,name,stale_days,last_activity,
 extract(epoch FROM (least($3,now())-last_activity))/86400 AS idle_days
FROM activity WHERE last_activity < least($3,now())-make_interval(days=>stale_days)
ORDER BY last_activity LIMIT 100
"""
)
LOSSES = (
    BASE
    + """
SELECT coalesce(nullif(l.lost_reason,''),'Não informado') AS reason,
 coalesce(s.name,'Entrada direta') AS from_stage,count(*) AS quantity,
 coalesce(sum(l.value_cents),0) AS value
FROM losses l LEFT JOIN kb_stages s ON s.account_id=$1 AND s.id=l.previous_stage_id
GROUP BY 1,2 ORDER BY quantity DESC,reason
"""
)
SOURCES = (
    BASE
    + """
SELECT coalesce(nullif(c.source,''),'Não informada') AS source,
 coalesce(nullif(c.campaign,''),'Não informada') AS campaign,
 count(*) FILTER(WHERE c.created_at >=$2) AS leads,
 count(w.card_id) AS wins,
 coalesce(100.0*count(w.card_id)/nullif(count(w.card_id)+count(l.card_id),0),0) AS
 win_rate,
 coalesce(sum(w.value_cents),0) AS revenue
FROM cards c LEFT JOIN wins w ON w.card_id=c.id LEFT JOIN losses l ON l.card_id=c.id
WHERE c.created_at >=$2 OR w.card_id IS NOT NULL OR l.card_id IS NOT NULL
GROUP BY 1,2 ORDER BY leads DESC,source,campaign
"""
)
TEAM = (
    BASE
    + """
SELECT c.assignee_id, c.assignee_name AS name,
 count(*) FILTER(WHERE c.created_at >=$2) AS leads,count(w.card_id) AS wins,
 coalesce(100.0*count(w.card_id)/nullif(count(w.card_id)+count(l.card_id),0),0) AS
 win_rate,
 coalesce(sum(w.value_cents),0) AS revenue,
 (SELECT count(*) FROM task_scope t WHERE (t.closed_at IS NULL OR t.closed_at >=$3)
 AND t.due_date < (least($3-interval '1 microsecond',now())
 AT TIME ZONE 'America/Sao_Paulo')::date
 AND t.contact_id IN (SELECT cs.contact_id FROM cards cs WHERE cs.assignee_id IS
 NOT DISTINCT FROM c.assignee_id)) AS overdue_tasks
FROM cards c LEFT JOIN wins w ON w.card_id=c.id LEFT JOIN losses l ON l.card_id=c.id
GROUP BY c.assignee_id,c.assignee_name ORDER BY revenue DESC,name
"""
)
TIMELINE = (
    BASE
    + """
SELECT d::date AS date,
 (SELECT count(*) FROM cards c WHERE (c.created_at AT TIME ZONE
 'America/Sao_Paulo')::date=d::date) AS leads,
 (SELECT count(*) FROM wins w WHERE (w.created_at AT TIME ZONE
 'America/Sao_Paulo')::date=d::date) AS wins
FROM generate_series(($2 AT TIME ZONE 'America/Sao_Paulo')::date,(($3 AT TIME ZONE
 'America/Sao_Paulo')::date-1),interval '1 day') d
ORDER BY d
"""
)
TEMPERATURE = (
    BASE
    + """
SELECT coalesce(nullif(temperature,''),'Não informada') AS name,count(*) AS quantity
FROM cards GROUP BY 1 ORDER BY quantity DESC
"""
)

ORIGINS = SOURCES.replace(
    "coalesce(nullif(c.campaign,''),'Não informada') AS campaign",
    "'Todas' AS campaign",
)
CAMPAIGNS = SOURCES.replace(
    "coalesce(nullif(c.source,''),'Não informada') AS source",
    "'Todas' AS source",
)
