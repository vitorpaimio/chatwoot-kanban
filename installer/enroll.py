"""Executado via pipe no container Kanban; não registrar o conteúdo recebido."""

import asyncio
import json
import sys

from app.database import close_pool, connection, init_pool
from app.security import encrypt


async def main() -> None:
    """Registra recursos com propriedade confirmada antes de habilitar o worker."""
    request = json.load(sys.stdin)
    receipt = request["receipt"]
    await init_pool()
    try:
        async with connection() as conn, conn.transaction():
            for account in receipt["accounts"]:
                await conn.execute(
                    """INSERT INTO kb_accounts
                    (account_id,token_cipher,attribute_mappings)
                    VALUES($1,$2,'{"origem":null,"campanha":null,"temperatura":null}')
                    ON CONFLICT(account_id) DO UPDATE
                    SET token_cipher=excluded.token_cipher,
                    enabled=true,activation_status='pending',activation_error=NULL,
                    activation_attempts=0,activation_next_attempt=now()""",
                    account,
                    encrypt(request["token"]),
                )
                resources = [
                    ("attribute", "contact:" + a["key"], a)
                    for a in receipt["attributes"]
                    if a["account"] == account
                ] + [
                    ("webhook", h["url"], h)
                    for h in receipt["webhooks"]
                    if h["account"] == account
                ]
                for kind, key, resource in resources:
                    await conn.execute(
                        """INSERT INTO kb_resources
                        (account_id,resource_type,resource_key,
                        remote_id,ownership,definition) VALUES($1,$2,$3,$4,$5,'{}')
                        ON CONFLICT(account_id,resource_type,resource_key) DO UPDATE
                        SET remote_id=excluded.remote_id,
                        ownership=excluded.ownership""",
                        account,
                        kind,
                        key,
                        resource["id"],
                        resource["ownership"],
                    )
    finally:
        await close_pool()


asyncio.run(main())
