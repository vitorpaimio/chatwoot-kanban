"""Sondas operacionais sem identificadores ou dados de clientes."""

import asyncio

from app.database import connection


async def health_status() -> dict:
    """Verifica banco, filas atrasadas e sinal independente do worker."""
    try:
        async with asyncio.timeout(3), connection() as conn:
            await conn.fetchval("SELECT 1")
            worker = await conn.fetchval(
                "SELECT EXISTS(SELECT 1 FROM kb_worker_heartbeat WHERE "
                "seen_at>now()-interval '120 seconds')"
            )
            queue = await conn.fetchrow(
                """SELECT count(*) AS pending,count(*) FILTER(WHERE stale) AS
                   delayed FROM (
                SELECT s.status='failed' OR s.next_attempt<now()-interval '10
                minutes' AS stale FROM
                kb_sync s
                JOIN kb_accounts a USING(account_id) WHERE a.enabled AND
                s.status<>'synced'
                UNION ALL SELECT d.status='failed' OR d.next_attempt<now()-interval
                '10 minutes' FROM
                kb_deliveries d
                JOIN kb_accounts a USING(account_id) WHERE a.enabled AND
                d.status<>'processed'
                UNION ALL SELECT a.activation_error IS NOT NULL FROM kb_accounts a
                WHERE a.enabled AND a.activation_status<>'ready'
                UNION ALL SELECT a.import_error IS NOT NULL FROM kb_accounts a
                WHERE a.enabled AND a.import_status IN
                ('pending','running','failed')
                UNION ALL SELECT true FROM kb_accounts a
                WHERE a.enabled AND a.reconcile_error IS NOT NULL) jobs"""
            )
            return {
                "status": "ok" if worker and not queue["delayed"] else "degraded",
                "database": "ok",
                "worker": "ok" if worker else "stopped",
                "queue": dict(queue),
            }
    except Exception:
        return {"status": "unavailable", "database": "unavailable", "worker": "unknown"}


async def worker_probe() -> bool:
    """Verifica o heartbeat do próprio host/container, mesmo com fila vazia."""
    import socket

    from app.database import close_pool, init_pool

    try:
        async with asyncio.timeout(5):
            await init_pool()
            async with connection() as conn:
                return bool(
                    await conn.fetchval(
                        "SELECT EXISTS(SELECT 1 FROM kb_worker_heartbeat "
                        "WHERE split_part(worker_id,':',1)=$1 "
                        "AND seen_at>now()-interval '120 seconds')",
                        socket.gethostname(),
                    )
                )
    except Exception:
        return False
    finally:
        await close_pool()


if __name__ == "__main__":
    raise SystemExit(0 if asyncio.run(worker_probe()) else 1)
