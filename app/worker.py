import asyncio
import logging

from app.chatwoot_client import Chatwoot
from app.database import (
    close_pool,
    connection,
    init_pool,
    lock_contact,
    lock_primary_contact,
    record,
)
from app.services import SYSTEM, projection, refresh_contact, setup_account

logger = logging.getLogger("kanban.worker")


async def work_enabled(conn, account: int) -> bool:
    """O bloqueio compartilhado dura até concluir a unidade; disable aguarda commit."""
    return bool(
        await conn.fetchval(
            "SELECT enabled FROM kb_accounts WHERE account_id=$1 FOR SHARE", account
        )
    )


async def tick():
    async with connection() as conn:
        accounts = await conn.fetch(
            """
        SELECT account_id FROM kb_accounts WHERE enabled AND
        activation_status= 'pending'
        """
        )
        for row in accounts:
            account = row["account_id"]
            locked = await conn.fetchval(
                "SELECT pg_try_advisory_lock(900000, $1)", account
            )
            if not locked:
                continue
            try:
                async with conn.transaction():
                    if not await work_enabled(conn, account):
                        continue
                    async with await Chatwoot.for_account(conn, account) as cw:
                        await setup_account(conn, cw)
            except Exception as exc:
                await conn.execute(
                    (
                        """
        UPDATE kb_accounts SET activation_status= 'failed'
        ,activation_error=$2 WHERE account_id=$1 AND enabled
        """
                    ),
                    account,
                    type(exc).__name__,
                )
                logger.warning("Ativação %s: %s", account, type(exc).__name__)
            finally:
                await conn.execute("SELECT pg_advisory_unlock(900000,$1)", account)
        deliveries = await conn.fetch(
            """
        SELECT id,account_id,contact_id FROM kb_deliveries WHERE account_id IN
        (SELECT account_id FROM kb_accounts WHERE enabled) AND status<>
        'processed' AND next_attempt<=now() ORDER BY id LIMIT 30
        """
        )
        for row in deliveries:
            async with conn.transaction():
                if not await work_enabled(conn, row["account_id"]):
                    continue
                delivery = await conn.fetchrow(
                    (
                        """
        SELECT * FROM kb_deliveries WHERE id=$1 AND status<> 'processed' FOR
        UPDATE SKIP LOCKED
        """
                    ),
                    row["id"],
                )
                if not delivery:
                    continue
                try:
                    async with conn.transaction():
                        if delivery["contact_id"]:
                            await lock_primary_contact(
                                conn, delivery["account_id"], delivery["contact_id"]
                            )
                            async with await Chatwoot.for_account(
                                conn, delivery["account_id"]
                            ) as cw:
                                await refresh_contact(conn, cw, delivery["contact_id"])
                        await conn.execute(
                            (
                                """
        UPDATE kb_deliveries SET status= 'processed'
        ,processed_at=now(),error=NULL WHERE id=$1
        """
                            ),
                            delivery["id"],
                        )
                except Exception as exc:
                    await conn.execute(
                        (
                            """
        UPDATE kb_deliveries SET status= 'failed'
        ,attempts=attempts+1,error=$2,next_attempt=now()+interval '30 seconds'
        WHERE id=$1
        """
                        ),
                        delivery["id"],
                        type(exc).__name__,
                    )
        expired = await conn.fetch(
            """
        SELECT account_id,contact_id FROM kb_tasks WHERE account_id IN
        (SELECT account_id FROM kb_accounts WHERE enabled) AND status= 'active' AND
        due_state<> CASE WHEN due_date<(now() AT TIME ZONE 'America/Sao_Paulo'
        )::date THEN 'overdue' WHEN due_date=(now() AT TIME ZONE
        'America/Sao_Paulo' )::date THEN 'today' ELSE 'active' END
        """
        )
        for task in expired:
            async with conn.transaction():
                if not await work_enabled(conn, task["account_id"]):
                    continue
                await lock_contact(conn, task["account_id"], task["contact_id"])
                await conn.execute(
                    (
                        """
        UPDATE kb_tasks SET due_state=CASE WHEN due_date<(now() AT TIME ZONE
        'America/Sao_Paulo' )::date THEN 'overdue' WHEN due_date=(now() AT
        TIME ZONE 'America/Sao_Paulo' )::date THEN 'today' ELSE 'active' END
        WHERE account_id=$1 AND contact_id=$2 AND status= 'active'
        """
                    ),
                    task["account_id"],
                    task["contact_id"],
                )
                await record(
                    conn,
                    task["account_id"],
                    task["contact_id"],
                    SYSTEM,
                    "vencimento_atualizado",
                )
        jobs = await conn.fetch(
            """
        SELECT account_id,contact_id FROM kb_sync WHERE account_id IN
        (SELECT account_id FROM kb_accounts WHERE enabled) AND status<> 'synced' AND
        next_attempt<=now() ORDER BY next_attempt LIMIT 30
        """
        )
        for job in jobs:
            account, contact = job["account_id"], job["contact_id"]
            async with conn.transaction():
                if not await work_enabled(conn, account):
                    continue
                await lock_contact(conn, account, contact)
                job = await conn.fetchrow(
                    (
                        """
        SELECT * FROM kb_sync WHERE account_id=$1 AND contact_id=$2 AND
        status<> 'synced' AND next_attempt<=now() FOR UPDATE SKIP LOCKED
        """
                    ),
                    account,
                    contact,
                )
                if not job:
                    continue
                try:
                    attributes = await projection(conn, account, contact)
                    async with await Chatwoot.for_account(conn, account) as cw:
                        await cw.request(
                            "PATCH",
                            f"/contacts/{contact}",
                            json={"custom_attributes": attributes},
                        )
                    await conn.execute(
                        (
                            """
        UPDATE kb_sync SET status= 'synced'
        ,synced_version=version,projection=$3,last_error=NULL,updated_at=now()
        WHERE account_id=$1 AND contact_id=$2
        """
                        ),
                        account,
                        contact,
                        attributes,
                    )
                    await record(
                        conn,
                        account,
                        contact,
                        SYSTEM,
                        "sincronizado",
                        after={"version": job["version"]},
                        sync=False,
                    )
                except Exception as exc:
                    delay = min(300, 2 ** min(job["attempts"] + 1, 8))
                    await conn.execute(
                        (
                            """
        UPDATE kb_sync SET status= 'failed'
        ,attempts=attempts+1,last_error=$3,next_attempt=now()+$4*interval
        '1 second' WHERE account_id=$1 AND contact_id=$2
        """
                        ),
                        account,
                        contact,
                        type(exc).__name__,
                        delay,
                    )
                    await record(
                        conn,
                        account,
                        contact,
                        SYSTEM,
                        "sincronizacao_falhou",
                        after={
                            "attempt": job["attempts"] + 1,
                            "error": type(exc).__name__,
                        },
                        sync=False,
                    )


async def main():
    logging.basicConfig(level=logging.INFO)
    await init_pool()
    try:
        while True:
            try:
                await tick()
            except Exception as exc:
                logger.error("Worker: %s", type(exc).__name__)
            await asyncio.sleep(2)
    finally:
        await close_pool()


if __name__ == "__main__":
    asyncio.run(main())
