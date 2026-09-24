"""Regressão da espera circular entre chaves do cache de métricas."""

import asyncio

from app.database import connection
from app.metrics.service import cached


async def test_cache_opposite_key_order_does_not_block_pool(db):
    barrier = asyncio.Barrier(2)

    async def fetch():
        return {"value": 1}

    async def request(first, second):
        async with connection() as conn, conn.transaction():
            assert await cached(conn, 1, first, fetch) == {"value": 1}
            await barrier.wait()
            assert await cached(conn, 1, second, fetch) == {"value": 1}

    await asyncio.wait_for(
        asyncio.gather(request("a", "b"), request("b", "a")), timeout=3
    )
    async with connection() as conn:
        assert (
            await conn.fetchval(
                "SELECT count(*) FROM kb_metrics_cache WHERE account_id=1"
            )
            == 2
        )

        async def unexpected_fetch():
            raise AssertionError("Cache válido não deve consultar o Chatwoot")

        assert await cached(conn, 1, "a", unexpected_fetch) == {"value": 1}
