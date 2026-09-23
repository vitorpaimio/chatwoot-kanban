"""Atualiza somente metadados dos contatos para os filtros de métricas."""

import asyncio

from app.chatwoot_client import Chatwoot
from app.database import close_pool, connection, init_pool, lock_contact
from app.services import refresh_contact


async def main():
    await init_pool()
    try:
        async with connection() as conn:
            rows = await conn.fetch(
                "SELECT account_id,contact_id FROM kb_contacts "
                "ORDER BY account_id,contact_id"
            )
            for row in rows:
                async with (
                    conn.transaction(),
                    await Chatwoot.for_account(conn, row["account_id"]) as cw,
                ):
                    await lock_contact(conn, row["account_id"], row["contact_id"])
                    await refresh_contact(
                        conn, cw, row["contact_id"], project_cards=False
                    )
            print(f"Metadados atualizados: {len(rows)} contatos. Cartões preservados.")
    finally:
        await close_pool()


if __name__ == "__main__":
    asyncio.run(main())
