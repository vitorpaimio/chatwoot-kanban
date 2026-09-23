"""Atualiza contas instaladas para usar o Kanban apenas no menu lateral."""

import asyncio

from app.chatwoot_client import Chatwoot
from app.database import close_pool, connection, init_pool
from app.services import remove_conversation_app


async def main():
    await init_pool()
    try:
        async with connection() as conn:
            accounts = await conn.fetch("SELECT account_id FROM kb_accounts")
            for row in accounts:
                async with await Chatwoot.for_account(conn, row["account_id"]) as cw:
                    await remove_conversation_app(conn, cw)
                print(f"Conta {row['account_id']}: acesso somente pelo menu lateral.")
    finally:
        await close_pool()


if __name__ == "__main__":
    asyncio.run(main())
