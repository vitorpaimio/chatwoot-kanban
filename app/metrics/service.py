"""Cache de cinco minutos e agregação SQL dos dados públicos do Chatwoot."""

from datetime import datetime
from zoneinfo import ZoneInfo

from app.chatwoot_client import Chatwoot
from app.config import settings


async def cached(conn, account, key, fetch):
    # A transação externa pode manter escritas de outras chaves do cache.
    # Nunca esperar outra transação aqui: ordens diferentes criariam um ciclo.
    async with conn.transaction():
        row = await conn.fetchrow(
            (
                "SELECT payload FROM kb_metrics_cache WHERE account_id=$1 AND"
                " cache_key=$2 AND fetched_at>now()-interval '5 minutes'"
            ),
            account,
            key,
        )
        if row:
            return row["payload"]
        writable = await conn.fetchval(
            "SELECT pg_try_advisory_xact_lock(hashtextextended($1, 0))",
            f"kanban:metrics:{account}:{key}",
        )
        payload = await fetch()
        if not writable:
            return payload
        await conn.execute(
            (
                "INSERT INTO kb_metrics_cache(account_id,cache_key,payload) V"
                "ALUES($1,$2,$3) ON CONFLICT(account_id,cache_key) DO UPDATE "
                "SET payload=excluded.payload,fetched_at=now()"
            ),
            account,
            key,
            payload,
        )
        return payload


async def native_options(conn, account):
    mappings = await conn.fetchval(
        "SELECT attribute_mappings FROM kb_accounts WHERE account_id=$1", account
    )

    async def fetch():
        async with await Chatwoot.for_account(conn, account) as cw:
            inboxes = await cw.request("GET", "/inboxes")
            agents = await cw.request("GET", "/agents")
            attributes = await cw.request("GET", "/custom_attribute_definitions")
            return {
                "temperature_declared": any(
                    a.get("attribute_key") == mappings.get("temperatura")
                    and a.get("attribute_model") in (1, "contact_attribute")
                    for a in attributes
                ),
                "inboxes": [
                    {"id": r["id"], "name": r["name"]}
                    for r in inboxes.get("payload", [])
                ],
                "agents": [
                    {"id": r["id"], "name": r["name"]}
                    for r in (
                        agents.get("payload", [])
                        if isinstance(agents, dict)
                        else agents
                    )
                ],
            }

    return await cached(
        conn, account, "options:v3:" + str(mappings.get("temperatura")), fetch
    )


async def service_data(conn, args):
    account, start, end, funnel, assignee, inbox = args

    async def conversations():
        rows, page = [], 1
        async with await Chatwoot.for_account(conn, account) as cw:
            while True:
                result = await cw.request(
                    "GET",
                    "/conversations",
                    params={"status": "all", "assignee_type": "all", "page": page},
                )
                batch = result.get("data", {}).get("payload", [])
                if not batch:
                    break
                for c in batch:
                    rows.append(
                        {
                            "id": c["id"],
                            "contact_id": c.get("meta", {}).get("sender", {}).get("id"),
                            "assignee_id": (
                                c.get("meta", {}).get("assignee") or {}
                            ).get("id"),
                            "inbox_id": c.get("inbox_id"),
                            "status": c.get("status"),
                            "created": c.get("created_at"),
                            "waiting": c.get("waiting_since") or None,
                            "first_reply": c.get("first_reply_created_at") or None,
                        }
                    )
                page += 1
        return rows

    conv = await cached(conn, account, "conversations", conversations)

    async def reports():
        params = {
            "type": "agent" if assignee else "inbox" if inbox else "account",
            "since": int(start.timestamp()),
            "until": int(end.timestamp()),
            "timezone_offset": -3,
            "group_by": "day",
        }
        if assignee or inbox:
            params["id"] = assignee or inbox
        events = []
        async with await Chatwoot.for_account(conn, account) as cw:
            base = settings.chatwoot_base_url + f"/api/v2/accounts/{account}/reports"
            summary = await cw.request("GET", base + "/summary", params=params)
            timeseries = await cw.request(
                "GET", base, params={**params, "metric": "conversations_count"}
            )
            for year in range(start.year, end.year + 1):
                bucket = int(
                    datetime(
                        year, 1, 1, tzinfo=ZoneInfo("America/Sao_Paulo")
                    ).timestamp()
                )
                for metric in ("avg_first_response_time", "avg_resolution_time"):
                    page = 1
                    while True:
                        result = await cw.request(
                            "GET",
                            base + "/drilldown",
                            params={
                                **params,
                                "metric": metric,
                                "bucket_timestamp": bucket,
                                "group_by": "year",
                                "page": page,
                                "per_page": 100,
                            },
                        )
                        batch = result.get("payload", [])
                        for row in batch:
                            c = row.get("conversation") or {}
                            events.append(
                                {
                                    "metric": metric,
                                    "value": row.get("metric_value"),
                                    "occurred": row.get("occurred_at"),
                                    "contact_id": c.get("contact_id"),
                                    "conversation_id": c.get("display_id")
                                    or c.get("id"),
                                    "inbox_id": c.get("inbox_id"),
                                    "assignee_id": c.get("assignee_id"),
                                }
                            )
                        if not batch or page * 100 >= result.get("meta", {}).get(
                            "total_count", 0
                        ):
                            break
                        page += 1
        return {"summary": summary, "timeseries": timeseries, "events": events}

    key = f"reports:{start.isoformat()}:{end.isoformat()}:{assignee}:{inbox}"
    report = await cached(conn, account, key, reports)
    options = await native_options(conn, account)
    if (
        await conn.fetchval("SELECT current_setting('kanban.role',true)")
        != "administrator"
    ):
        allowed = {
            r["conversation_id"]
            for r in await conn.fetch(
                "SELECT conversation_id FROM kb_visible_cards WHERE account_id=$1",
                account,
            )
            if r["conversation_id"]
        }
        conv = [c for c in conv if c["id"] in allowed]
        report = {
            **report,
            "events": [
                e for e in report["events"] if e.get("conversation_id") in allowed
            ],
        }
    sql = """
    WITH conv AS (
      SELECT * FROM jsonb_to_recordset($7::jsonb) AS r(id integer,contact_id
 integer,assignee_id integer,inbox_id integer,status text,created double precision,
 waiting double precision,first_reply double precision)
      WHERE ($5::integer IS NULL OR assignee_id=$5) AND ($6::integer IS NULL OR
 inbox_id=$6)
      AND ($4::bigint IS NULL OR EXISTS(SELECT 1 FROM kb_visible_cards c WHERE
 c.account_id=$1 AND c.funnel_id=$4 AND c.contact_id=r.contact_id))
    ), events AS (
      SELECT * FROM jsonb_to_recordset($8::jsonb) AS r(metric text,value numeric,
 occurred double precision,contact_id integer,assignee_id integer,inbox_id integer)
      WHERE to_timestamp(occurred)>=$2 AND to_timestamp(occurred)<$3
      AND ($5::integer IS NULL OR assignee_id=$5) AND ($6::integer IS NULL OR
 inbox_id=$6)
      AND ($4::bigint IS NULL OR EXISTS(SELECT 1 FROM kb_visible_cards c WHERE
 c.account_id=$1 AND c.funnel_id=$4 AND c.contact_id=r.contact_id))
    )
    SELECT jsonb_build_object(
      'conversations',(SELECT count(*) FROM conv WHERE to_timestamp(created)>=$2
 AND to_timestamp(created)<$3),
      'open',(SELECT count(*) FROM conv WHERE status='open'),
      'unanswered',(SELECT count(*) FROM conv WHERE status='open' AND (waiting IS
 NOT NULL OR first_reply IS NULL)),
      'first_response_seconds',(SELECT avg(value) FROM events WHERE
 metric='avg_first_response_time'),
      'resolution_seconds',(SELECT avg(value) FROM events WHERE
 metric='avg_resolution_time'),
      'longest_wait',(SELECT row_to_json(w) FROM (SELECT id,to_timestamp(waiting)
 AS since,extract(epoch FROM now())-waiting AS seconds FROM conv WHERE
 status='open' AND waiting IS NOT NULL ORDER BY waiting LIMIT 1) w),
      'inboxes',(SELECT coalesce(jsonb_agg(i),'[]') FROM (SELECT inbox_id,count(*)
 AS quantity FROM conv WHERE to_timestamp(created)>=$2 AND to_timestamp(created)<$3
 GROUP BY inbox_id ORDER BY count(*) DESC) i),
      'agents',(SELECT coalesce(jsonb_agg(a),'[]') FROM (SELECT assignee_id,
 avg(value) AS first_response_seconds FROM events WHERE
 metric='avg_first_response_time' GROUP BY assignee_id) a)
    )
    """
    result = await conn.fetchval(sql, *args, conv, report["events"])
    names = {i["id"]: i["name"] for i in options["inboxes"]}
    for row in result["inboxes"]:
        row["name"] = names.get(row["inbox_id"], "Caixa não identificada")
    result["cache_seconds"] = 300
    result["live_note"] = (
        "Abertas, sem resposta e maior espera são a situação atual (c"
        "ache de até 5 min). Não há histórico anterior desses saldos "
        "na API do Chatwoot."
    )
    return result
