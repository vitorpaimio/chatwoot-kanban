"""Recebe credencial técnica via stdin e a cifra no banco do laboratório."""

import asyncio
import json
import sys

from app.database import close_pool, connection, init_pool
from app.security import encrypt


async def main() -> None:
    """Registra conta pendente para provisionamento pelo worker existente."""
    credential = json.load(sys.stdin)
    if credential["account"] != 1:
        raise ValueError("Este roteiro é exclusivo da conta 1 do laboratório")
    await init_pool()
    try:
        async with connection() as conn, conn.transaction():
            await conn.execute(
                """INSERT INTO kb_accounts(account_id,token_cipher,attribute_mappings)
                VALUES($1,$2,'{"origem":null,"campanha":null,"temperatura":null}')
                ON CONFLICT(account_id) DO UPDATE
                SET token_cipher=excluded.token_cipher""",
                credential["account"],
                encrypt(credential["token"]),
            )
    finally:
        await close_pool()


asyncio.run(main())
