"""Evolução observada dos funis, sem reconstruir posições anteriores à importação."""

from datetime import timedelta

from fastapi import HTTPException


async def evolution(conn, account, funnel_id, days):
    if funnel_id is not None and not await conn.fetchval(
        "SELECT 1 FROM kb_funnels WHERE account_id=$1 AND id=$2 AND NOT archived",
        account,
        funnel_id,
    ):
        raise HTTPException(404, "Funil não encontrado nesta conta")
    result = await conn.fetchrow(
        """
        WITH events AS (
        SELECT h.id,h.contact_id,ct.name AS contact_name,
        h.actor_id,h.actor_name,h.action,
        h.created_at,h.funnel_id,f.name AS funnel_name,s.name AS stage_name,
        old.name AS previous_stage,
        CASE WHEN h.action IN ('contato_importado','cartao_criado')
          THEN 'entry' ELSE 'move' END AS event_kind
        FROM kb_history h
        JOIN kb_funnels f ON (f.account_id,f.id)=(h.account_id,h.funnel_id)
        LEFT JOIN kb_contacts ct ON
          (ct.account_id,ct.contact_id)=(h.account_id,h.contact_id)
        LEFT JOIN kb_stages s ON (s.account_id,s.id)=(h.account_id,h.stage_id)
        LEFT JOIN kb_stages old ON old.account_id=h.account_id
          AND old.id::text=h.before_state->>'stage_id'
        WHERE h.account_id=$1 AND NOT f.archived
          AND ($2::bigint IS NULL OR h.funnel_id=$2)
          AND h.created_at >= ((now() AT TIME ZONE 'America/Sao_Paulo')::date
              - ($3::integer-1))::timestamp AT TIME ZONE 'America/Sao_Paulo'
          AND h.created_at <= now()
          AND (h.action IN ('contato_importado','cartao_criado',
              'movimento_externo','etapa_arquivada_movimento') OR
            (h.action='cartao_movido' AND
             h.before_state->>'stage_id' IS DISTINCT FROM
             h.after_state->>'stage_id'))
        )
        SELECT
          (SELECT coalesce(jsonb_agg(r), '[]'::jsonb) FROM
            (SELECT * FROM events ORDER BY created_at DESC,id DESC LIMIT 20) r
          ) AS recent,
          (SELECT coalesce(jsonb_agg(d), '[]'::jsonb) FROM
            (SELECT (created_at AT TIME ZONE 'America/Sao_Paulo')::date AS date,
              count(*) FILTER(WHERE event_kind='entry') AS entries,
              count(*) FILTER(WHERE event_kind='move') AS moves
             FROM events GROUP BY 1 ORDER BY 1) d
          ) AS daily,
          (SELECT count(DISTINCT contact_id) FROM events
            WHERE event_kind='move') AS moved_contacts,
          (SELECT coalesce(jsonb_agg(a), '[]'::jsonb) FROM
            (SELECT actor_id,coalesce(actor_name,'Sistema') AS name,
              count(*) AS moves FROM events WHERE event_kind='move'
             GROUP BY actor_id,actor_name ORDER BY count(*) DESC) a
          ) AS agents
        """,
        account,
        funnel_id,
        days,
    )
    today = await conn.fetchval("SELECT (now() AT TIME ZONE 'America/Sao_Paulo')::date")
    start = today - timedelta(days=days - 1)
    buckets = {
        start + timedelta(days=i): {"entries": 0, "moves": 0} for i in range(days)
    }
    observed = {row["date"]: row for row in result["daily"]}
    for day, bucket in buckets.items():
        row = observed.get(day.isoformat(), {})
        bucket.update(entries=row.get("entries", 0), moves=row.get("moves", 0))
    return {
        "start": start,
        "end": today,
        "timezone": "America/Sao_Paulo",
        "entries": sum(day["entries"] for day in buckets.values()),
        "moves": sum(day["moves"] for day in buckets.values()),
        "moved_contacts": result["moved_contacts"],
        "daily": [{"date": day, **values} for day, values in buckets.items()],
        "recent": result["recent"],
        "agents": result["agents"],
    }
