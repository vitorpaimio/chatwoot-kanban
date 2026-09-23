import json
from contextlib import asynccontextmanager

import asyncpg
from fastapi import HTTPException

from app.config import settings

pool: asyncpg.Pool | None = None


async def configure(connection):
    for typ in ("json", "jsonb"):
        await connection.set_type_codec(
            typ, schema="pg_catalog", encoder=json.dumps, decoder=json.loads
        )


async def init_pool():
    global pool
    pool = await asyncpg.create_pool(
        settings.database_url, init=configure, min_size=1, max_size=10
    )


async def close_pool():
    if pool:
        await pool.close()


@asynccontextmanager
async def connection(user=None):
    if pool is None:
        raise RuntimeError("Banco indisponível")
    async with pool.acquire() as conn:
        if user is None:
            yield conn
            return
        async with conn.transaction():
            await require_enabled(conn, user["account"])
            for key, value in {
                "account": str(user["account"]),
                "actor": str(user["id"]),
                "role": user["role"],
                "inboxes": json.dumps(user.get("inboxes", [])),
            }.items():
                await conn.execute(
                    "SELECT set_config($1,$2,true)", "kanban." + key, value
                )
            yield conn


async def require_enabled(conn, account: int) -> None:
    """Serializa desativação com requisições e unidades de trabalho em andamento."""
    enabled = await conn.fetchval(
        "SELECT enabled FROM kb_accounts WHERE account_id=$1 FOR SHARE", account
    )
    if not enabled:
        raise HTTPException(403, "Conta não habilitada para o Kanban")


async def notify(conn, account):
    await conn.execute("SELECT pg_notify('kanban_events', $1)", str(account))


async def lock_contact(conn, account, contact):
    await conn.execute("SELECT pg_advisory_xact_lock($1, $2)", account, contact)


async def record(
    conn,
    account,
    contact,
    actor,
    action,
    before=None,
    after=None,
    funnel=None,
    stage=None,
    sync=True,
):
    await conn.execute(
        (
            """
        INSERT INTO kb_history
        (account_id,contact_id,actor_id,actor_name,action,before_state,after_state,
        funnel_id,stage_id) VALUES($1,$2,$3,$4,$5,$6,$7,$8,$9)
        """
        ),
        account,
        contact,
        actor["id"],
        actor["name"],
        action,
        before,
        after,
        funnel,
        stage,
    )
    if sync and contact:
        await conn.execute(
            """
        INSERT INTO kb_sync(account_id,contact_id) VALUES($1,$2) ON
        CONFLICT(account_id,contact_id) DO UPDATE SET
        version=kb_sync.version+1, status= 'pending' , attempts=0,
        next_attempt=now(), last_error=NULL
        """,
            account,
            contact,
        )
    await notify(conn, account)


async def lock_primary_contact(conn, account, contact):
    """Ordena importações com arquivamento e movimentações do funil principal."""
    await conn.execute(
        """SELECT id FROM kb_funnels
        WHERE account_id=$1 AND is_primary FOR UPDATE""",
        account,
    )
    await lock_contact(conn, account, contact)
