"""Processamento limitado por conta com checkpoints e heartbeat independente da fila."""

import asyncio
import logging
import os
import socket
import uuid

import httpx

from app.chatwoot_client import Chatwoot, failure
from app.database import (
    close_pool,
    connection,
    init_pool,
    lock_contact,
    lock_primary_contact,
    record,
)
from app.provisioning.attributes import AttributeConflictError
from app.recovery import import_one, reconcile_one
from app.services import SYSTEM, projection, refresh_contact, setup_account

logger = logging.getLogger("kanban.worker")
WORKER_ID = f"{socket.gethostname()}:{os.getpid()}:{uuid.uuid4()}"


async def heartbeat(conn):
    await conn.execute(
        """INSERT INTO kb_worker_heartbeat(worker_id) VALUES($1)
        ON CONFLICT(worker_id) DO UPDATE SET seen_at=now()""",
        WORKER_ID,
    )
    await conn.execute(
        "DELETE FROM kb_worker_heartbeat WHERE seen_at<now()-interval '1 day'"
    )


async def work_enabled(conn, account: int) -> bool:
    """Serializa cada unidade com a desativação da conta."""
    return bool(
        await conn.fetchval(
            "SELECT enabled AND activation_status='ready' FROM kb_accounts WHERE "
            "account_id=$1 FOR SHARE",
            account,
        )
    )


async def defer_remote(conn, account, exc, delay):
    if isinstance(exc, httpx.HTTPStatusError) and exc.response.status_code in (
        401,
        403,
        429,
    ):
        await conn.execute(
            "UPDATE kb_accounts SET remote_next_attempt=now()+$2*interval '1 "
            "second' WHERE account_id=$1",
            account,
            delay,
        )


async def remote_available(conn, account):
    return await conn.fetchval(
        "SELECT enabled AND remote_next_attempt<=now() FROM kb_accounts WHERE "
        "account_id=$1",
        account,
    )


async def process_delivery(conn, cw, row):
    if not await remote_available(conn, cw.account):
        return
    deferred = None
    async with conn.transaction():
        if not await work_enabled(conn, cw.account):
            return
        await lock_primary_contact(conn, cw.account, row["contact_id"] or 0)
        try:
            async with conn.transaction():
                if row["contact_id"]:
                    await refresh_contact(conn, cw, row["contact_id"])
                await conn.execute(
                    "UPDATE kb_deliveries SET "
                    "status='processed',processed_at=now(),error=NULL WHERE id=$1",
                    row["id"],
                )
        except Exception as exc:
            diagnostic, delay = failure(exc, row["attempts"])
            deferred = (exc, delay)
            await conn.execute(
                """UPDATE kb_deliveries SET
                   status='failed',attempts=attempts+1,error=$2,
                next_attempt=now()+$3*interval '1 second' WHERE id=$1""",
                row["id"],
                diagnostic,
                delay,
            )

    if deferred:
        await defer_remote(conn, cw.account, *deferred)


async def process_sync(conn, cw, job):
    account, contact = cw.account, job["contact_id"]
    if not await remote_available(conn, account):
        return
    deferred = None
    async with conn.transaction():
        if not await work_enabled(conn, account):
            return
        await lock_contact(conn, account, contact)
        job = await conn.fetchrow(
            "SELECT * FROM kb_sync WHERE account_id=$1 AND contact_id=$2 FOR UPDATE",
            account,
            contact,
        )
        if job["status"] == "synced":
            return
        try:
            attributes = await projection(conn, account, contact)
            await cw.request(
                "PATCH", f"/contacts/{contact}", json={"custom_attributes": attributes}
            )
            await conn.execute(
                """UPDATE kb_sync SET
                   status='synced',synced_version=version,projection=$3,
                attempts=0,last_error=NULL,updated_at=now() WHERE account_id=$1 AND
                contact_id=$2""",
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
            diagnostic, delay = failure(exc, job["attempts"])
            deferred = (exc, delay)
            await conn.execute(
                """UPDATE kb_sync SET
                   status='failed',attempts=attempts+1,last_error=$3,
                next_attempt=now()+$4*interval '1 second' WHERE account_id=$1 AND
                contact_id=$2""",
                account,
                contact,
                diagnostic,
                delay,
            )
            await record(
                conn,
                account,
                contact,
                SYSTEM,
                "sincronizacao_falhou",
                after={"attempt": job["attempts"] + 1, "error": diagnostic},
                sync=False,
            )

    if deferred:
        await defer_remote(conn, account, *deferred)


async def expire(conn, account, limit):
    tasks = await conn.fetch(
        """SELECT contact_id FROM kb_tasks WHERE account_id=$1 AND status='active'
        AND due_state<>CASE WHEN due_date<(now() AT TIME ZONE 'America/Sao_Paulo')::date
        THEN 'overdue' WHEN due_date=(now() AT TIME ZONE 'America/Sao_Paulo')::date
        THEN 'today' ELSE 'active' END ORDER BY id LIMIT $2""",
        account,
        limit,
    )
    for task in tasks:
        async with conn.transaction():
            if not await work_enabled(conn, account):
                return
            await lock_contact(conn, account, task["contact_id"])
            changed = await conn.fetchval(
                """UPDATE kb_tasks SET due_state=CASE
                WHEN due_date<(now() AT TIME ZONE 'America/Sao_Paulo')::date THEN
                'overdue'
                WHEN due_date=(now() AT TIME ZONE 'America/Sao_Paulo')::date THEN
                'today'
                ELSE 'active' END WHERE account_id=$1 AND contact_id=$2 AND
                status='active'
                RETURNING id""",
                account,
                task["contact_id"],
            )
            if changed:
                await record(
                    conn, account, task["contact_id"], SYSTEM, "vencimento_atualizado"
                )
        await heartbeat(conn)


async def recovery_batch(conn, cw, kind, limit):
    if not await remote_available(conn, cw.account):
        return
    row = await conn.fetchrow(
        "SELECT * FROM kb_accounts WHERE account_id=$1", cw.account
    )
    from datetime import UTC, datetime

    if row[f"{kind}_next_attempt"] > datetime.now(UTC):
        return
    if kind == "import" and row["import_status"] not in (
        "pending",
        "running",
        "failed",
    ):
        return
    for _ in range(limit):
        try:
            more = await (
                import_one(conn, cw) if kind == "import" else reconcile_one(conn, cw)
            )
        except Exception as exc:
            diagnostic, delay = failure(exc, row[f"{kind}_attempts"])
            await defer_remote(conn, cw.account, exc, delay)
            # kind vem apenas das duas chamadas internas, nunca de entrada externa.
            await conn.execute(
                f"""UPDATE kb_accounts SET {kind}_error=$2,
                {kind}_attempts={kind}_attempts+1,
                {kind}_next_attempt=now()+$3*interval '1 second'
                {",import_status='failed'" if kind == "import" else ""}
                WHERE account_id=$1""",
                cw.account,
                diagnostic,
                delay,
            )
            break
        await heartbeat(conn)
        if not more:
            break


async def tick():
    async with connection() as conn:
        await heartbeat(conn)
        accounts = await conn.fetch(
            "SELECT account_id FROM kb_accounts WHERE enabled ORDER BY account_id"
        )
        for account_row in accounts:
            account = account_row["account_id"]
            if not await conn.fetchval(
                "SELECT pg_try_advisory_lock(900000,$1)", account
            ):
                continue
            try:
                row = await conn.fetchrow(
                    "SELECT * FROM kb_accounts WHERE account_id=$1", account
                )
                if not row["enabled"]:
                    continue
                async with await Chatwoot.for_account(conn, account) as cw:
                    if row["activation_status"] == "pending":
                        from datetime import UTC, datetime

                        if row["activation_next_attempt"] > datetime.now(UTC):
                            continue
                        try:
                            await setup_account(conn, cw, progress=heartbeat)
                        except Exception as exc:
                            diagnostic, delay = failure(exc, row["activation_attempts"])
                            await conn.execute(
                                """UPDATE kb_accounts SET
                                   activation_status=$2,activation_error=$3,
                                activation_attempts=activation_attempts+1,
                                activation_next_attempt=now()+$4*interval '1 second'
                                WHERE account_id=$1""",
                                account,
                                "failed"
                                if isinstance(exc, AttributeConflictError)
                                else "pending",
                                diagnostic,
                                delay,
                            )
                            continue
                    elif row["activation_status"] != "ready":
                        continue
                    limit = row["processing_limit"]
                    deliveries = await conn.fetch(
                        """SELECT * FROM kb_deliveries WHERE account_id=$1 AND
                           status<>'processed'
                        AND next_attempt<=now() ORDER BY id LIMIT $2""",
                        account,
                        limit,
                    )
                    for delivery in deliveries:
                        await process_delivery(conn, cw, delivery)
                        await heartbeat(conn)
                    await expire(conn, account, limit)
                    await recovery_batch(conn, cw, "import", limit)
                    await recovery_batch(conn, cw, "reconcile", limit)
                    jobs = await conn.fetch(
                        """SELECT * FROM kb_sync WHERE account_id=$1 AND
                           status<>'synced'
                        AND next_attempt<=now() ORDER BY next_attempt,contact_id
                        LIMIT $2""",
                        account,
                        limit,
                    )
                    for job in jobs:
                        await process_sync(conn, cw, job)
                        await heartbeat(conn)
            except Exception as exc:
                logger.warning("Conta %s: %s", account, type(exc).__name__)
            finally:
                await conn.execute("SELECT pg_advisory_unlock(900000,$1)", account)
                await heartbeat(conn)


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
