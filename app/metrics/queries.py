"""Agregações temporais no PostgreSQL; limites de data são semiabertos.

A taxa de tarefas no prazo devolve nulo quando nenhuma tarefa foi concluída, para
a interface mostrar "—" em vez de um 0% enganoso.
"""

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
 FROM kb_visible_cards c JOIN snapshot s ON s.card_id=c.id
 JOIN kb_funnels f ON (f.account_id,f.id)=(c.account_id,c.funnel_id)
 JOIN kb_contacts ct ON (ct.account_id,ct.contact_id)=(c.account_id,c.contact_id)
 LEFT JOIN kb_agents a ON a.account_id=c.account_id AND a.user_id=s.assignee_id
 WHERE c.account_id=$1 AND ($4::bigint IS NULL OR c.funnel_id=$4)
 AND ($5::integer IS NULL OR s.assignee_id=$5)
 AND ($6::integer IS NULL OR s.inbox_id=$6)
), events AS (
 SELECT e.* FROM kb_card_events e JOIN cards c ON c.id=e.card_id
 WHERE e.account_id=$1 AND e.created_at<$3 AND e.created_at<=now()
), stays AS (
 SELECT e.*,lead(e.created_at) OVER(PARTITION BY e.card_id ORDER BY e.created_at,e.id)
 AS left_at FROM events e WHERE e.event_type IN ('created','moved')
), entries AS (
 -- Valor da passagem pela etapa: o último registrado antes de sair dela, não o da
 -- entrada. Ganhar e depois informar o valor é o fluxo comum.
 SELECT st.id,st.account_id,st.card_id,st.event_type,st.stage_id,
 st.previous_stage_id,st.stage_kind,st.stage_position,
 coalesce((SELECT v.value_cents FROM events v WHERE v.card_id=st.card_id
 AND (v.created_at,v.id)>=(st.created_at,st.id)
 AND (st.left_at IS NULL OR v.created_at<st.left_at)
 ORDER BY v.created_at DESC,v.id DESC LIMIT 1),st.value_cents) AS value_cents,
 st.lost_reason,st.assignee_id,st.inbox_id,st.source,st.campaign,st.temperature,
 st.entered_at,st.created_at,st.left_at
 FROM stays st
), wins AS (
 SELECT DISTINCT ON(card_id) * FROM entries WHERE stage_kind='won' AND created_at >=$2
 ORDER BY card_id,created_at DESC,id DESC
), losses AS (
 SELECT DISTINCT ON(card_id) * FROM entries WHERE stage_kind='lost' AND created_at
 >=$2
 ORDER BY card_id,created_at DESC,id DESC
), task_scope AS (
 SELECT t.* FROM kb_tasks t WHERE t.account_id=$1 AND t.created_at<$3
 AND (($4::bigint IS NULL AND $5::integer IS NULL AND $6::integer IS NULL)
 OR EXISTS(SELECT 1 FROM cards c WHERE c.contact_id=t.contact_id))
)
"""
PROBABILITIES = """
, probabilities AS (
 -- Chance histórica: das negociações que passaram pela etapa e já fecharam,
 -- quantas foram ganhas.
 SELECT x.stage_id,count(DISTINCT x.card_id) FILTER(WHERE cx.stage_kind='won')
 ::numeric/nullif(count(DISTINCT x.card_id) FILTER(WHERE cx.stage_kind IN
 ('won','lost')),0) AS chance
 FROM entries x JOIN cards cx ON cx.id=x.card_id GROUP BY x.stage_id
)
"""
SUMMARY = (
    BASE
    + PROBABILITIES
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
 JOIN cards c ON c.id=w.card_id) AS cycle_days,
 (SELECT coalesce(round(sum(c.value_cents*coalesce(pr.chance,0))),0) FROM cards c
 LEFT JOIN probabilities pr ON pr.stage_id=c.stage_id WHERE c.stage_kind='open')
 AS forecast
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
 100.0*count(*) FILTER(WHERE closed_at >=$2 AND closed_at<$3 AND
 (closed_at AT TIME ZONE 'America/Sao_Paulo')::date<=due_date)/nullif(count(*)
 FILTER(WHERE closed_at >=$2 AND closed_at<$3),0) AS on_time_rate
FROM task_scope
"""
)
FUNNEL = (
    BASE
    + PROBABILITIES
    + """
, cohorts AS (
 SELECT DISTINCT ON(card_id,stage_id) * FROM entries WHERE created_at >=$2
 ORDER BY card_id,stage_id,created_at,id
), spans AS (
 SELECT e.*,lead(created_at) OVER(PARTITION BY card_id ORDER BY created_at,id) AS
 exited_at FROM entries e
)
SELECT s.id,s.funnel_id,f.name AS funnel,s.name,s.position,s.color,s.kind,
 count(co.card_id) AS quantity,coalesce(sum(co.value_cents),0) AS value,
 coalesce(100.0*count(co.card_id) FILTER(WHERE EXISTS(
 SELECT 1 FROM kb_card_events later JOIN kb_stages ls ON
 (ls.account_id,ls.id)=(later.account_id,later.stage_id)
 WHERE later.account_id=$1 AND later.card_id=co.card_id
 AND later.event_type IN ('created','moved') AND (later.created_at,
 later.id)>(co.created_at,co.id) AND later.created_at<=now()
 AND ls.kind<>'lost' AND (ls.position,ls.id)>(s.position,s.id)
 ))/nullif(count(co.card_id),0),0) AS conversion,
 coalesce(100.0*count(co.card_id) FILTER(WHERE EXISTS(
 SELECT 1 FROM kb_card_events later JOIN kb_stages ls ON
 (ls.account_id,ls.id)=(later.account_id,later.stage_id)
 WHERE later.account_id=$1 AND later.card_id=co.card_id
 AND later.event_type IN ('created','moved') AND (later.created_at,
 later.id)>(co.created_at,co.id) AND later.created_at<=now()
 AND ls.kind='lost'
 ))/nullif(count(co.card_id),0),0) AS loss_rate,
 coalesce(100.0*count(co.card_id) FILTER(WHERE EXISTS(
 SELECT 1 FROM kb_card_events later WHERE later.account_id=$1 AND
 later.card_id=co.card_id
 AND later.event_type IN ('created','moved') AND (later.created_at,
 later.id)>(co.created_at,co.id)
 AND later.created_at<=now() AND later.stage_id=(SELECT ns.id FROM kb_stages ns
 WHERE ns.account_id=$1 AND ns.funnel_id=s.funnel_id AND NOT ns.archived
 AND ns.kind<>'lost' AND (ns.position,ns.id)>(s.position,s.id)
 ORDER BY ns.position,ns.id LIMIT 1)
 ))/nullif(count(co.card_id),0),0) AS next_conversion,
 (SELECT avg(extract(epoch FROM (sp.exited_at-sp.created_at))/86400) FROM spans sp
 WHERE sp.stage_id=s.id AND sp.exited_at >=$2 AND sp.exited_at<$3) AS dwell_days,
 (SELECT 100*chance FROM probabilities pr WHERE pr.stage_id=s.id) AS win_probability
FROM kb_stages s JOIN kb_funnels f ON (f.account_id,f.id)=(s.account_id,s.funnel_id)
LEFT JOIN cohorts co ON co.stage_id=s.id
WHERE s.account_id=$1 AND ($4::bigint IS NULL OR s.funnel_id=$4)
GROUP BY s.id,f.name ORDER BY s.funnel_id,s.position,s.id
"""
)
FLOW = (
    BASE
    + """
, cohort AS (
 SELECT id FROM cards WHERE created_at >=$2
), reach AS (
 SELECT DISTINCT e.card_id,t.funnel_id,t.kind,t.position,t.id AS stage_id
 FROM entries e JOIN cohort c ON c.id=e.card_id
 JOIN kb_stages t ON (t.account_id,t.id)=($1,e.stage_id)
)
-- Leads do período que chegaram a cada etapa aberta (ou além) e ao ganho.
-- Etapas de perda ficam fora: a passagem só mede avanço.
SELECT * FROM (
 SELECT s.id,s.funnel_id,s.name,s.color,s.kind,s.position,
 (SELECT count(DISTINCT r.card_id) FROM reach r WHERE r.funnel_id=s.funnel_id
 AND (r.kind='won' OR (r.kind='open' AND (r.position,r.stage_id)>=(s.position,s.id))))
 AS reached
 FROM kb_stages s JOIN kb_funnels f ON (f.account_id,f.id)=(s.account_id,s.funnel_id)
 WHERE s.account_id=$1 AND ($4::bigint IS NULL OR s.funnel_id=$4)
 AND NOT s.archived AND NOT f.archived AND s.kind='open'
 UNION ALL
 SELECT NULL,f.id,'Ganho',NULL,'won',NULL,
 (SELECT count(DISTINCT r.card_id) FROM reach r WHERE r.funnel_id=f.id
 AND r.kind='won')
 FROM kb_funnels f WHERE f.account_id=$1 AND ($4::bigint IS NULL OR f.id=$4)
 AND NOT f.archived
) steps ORDER BY funnel_id,position NULLS LAST,id
"""
)
STALE = (
    BASE
    + """
, latest_entry AS (
 SELECT card_id,max(created_at) AS happened FROM entries GROUP BY card_id
), latest_task AS (
 SELECT contact_id,max(closed_at) AS happened FROM task_scope
 WHERE closed_at<$3 GROUP BY contact_id
), activity AS (
 -- Mensagem do cliente também é atividade: quem conversa todo dia não está parado.
 SELECT c.*,greatest(c.created_at,e.happened,t.happened,
 CASE WHEN ct.last_activity_at<least($3,now()) THEN ct.last_activity_at END)
 AS last_activity
 FROM cards c LEFT JOIN latest_entry e ON e.card_id=c.id
 LEFT JOIN latest_task t ON t.contact_id=c.contact_id
 JOIN kb_contacts ct ON (ct.account_id,ct.contact_id)=($1,c.contact_id)
 WHERE c.stage_kind='open'
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
, people AS (
 -- Ganho e perda ficam com quem era responsável ao fechar, não com o atual.
 SELECT assignee_id FROM cards WHERE created_at >=$2
 UNION SELECT assignee_id FROM wins UNION SELECT assignee_id FROM losses
)
SELECT p.assignee_id,
 coalesce((SELECT a.name FROM kb_agents a WHERE a.account_id=$1
 AND a.user_id=p.assignee_id),(SELECT c.assignee_name FROM cards c
 WHERE c.assignee_id IS NOT DISTINCT FROM p.assignee_id LIMIT 1),
 CASE WHEN p.assignee_id IS NULL THEN 'Não atribuído'
 ELSE 'Agente '||p.assignee_id END) AS name,
 (SELECT count(*) FROM cards c WHERE c.created_at >=$2
 AND c.assignee_id IS NOT DISTINCT FROM p.assignee_id) AS leads,
 (SELECT count(*) FROM wins w WHERE w.assignee_id IS NOT DISTINCT FROM
 p.assignee_id) AS wins,
 coalesce(100.0*(SELECT count(*) FROM wins w WHERE w.assignee_id IS NOT DISTINCT
 FROM p.assignee_id)/nullif((SELECT count(*) FROM wins w WHERE w.assignee_id IS NOT
 DISTINCT FROM p.assignee_id)+(SELECT count(*) FROM losses l WHERE l.assignee_id IS
 NOT DISTINCT FROM p.assignee_id),0),0) AS win_rate,
 (SELECT coalesce(sum(w.value_cents),0) FROM wins w WHERE w.assignee_id IS NOT
 DISTINCT FROM p.assignee_id) AS revenue,
 (SELECT count(*) FROM task_scope t WHERE (t.closed_at IS NULL OR t.closed_at >=$3)
 AND t.due_date < (least($3-interval '1 microsecond',now())
 AT TIME ZONE 'America/Sao_Paulo')::date
 AND t.contact_id IN (SELECT cs.contact_id FROM cards cs WHERE cs.assignee_id IS
 NOT DISTINCT FROM p.assignee_id)) AS overdue_tasks
FROM people p ORDER BY revenue DESC,name
"""
)
TIMELINE = (
    BASE
    + """
SELECT d::date AS date,
 (SELECT count(*) FROM cards c WHERE (c.created_at AT TIME ZONE
 'America/Sao_Paulo')::date=d::date) AS leads,
 (SELECT count(*) FROM wins w WHERE (w.created_at AT TIME ZONE
 'America/Sao_Paulo')::date=d::date) AS wins,
 (SELECT coalesce(sum(w.value_cents),0) FROM wins w WHERE (w.created_at AT TIME ZONE
 'America/Sao_Paulo')::date=d::date) AS revenue,
 (SELECT count(*) FROM losses l WHERE (l.created_at AT TIME ZONE
 'America/Sao_Paulo')::date=d::date) AS losses,
 (SELECT coalesce(sum(l.value_cents),0) FROM losses l WHERE (l.created_at AT TIME
 ZONE 'America/Sao_Paulo')::date=d::date) AS lost_value
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
