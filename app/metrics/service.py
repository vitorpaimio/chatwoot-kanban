"""Cache de cinco minutos e agregação SQL dos dados públicos do Chatwoot."""


from app.chatwoot_client import Chatwoot


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
