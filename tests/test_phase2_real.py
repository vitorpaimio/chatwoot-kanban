"""Integração opt-in com Rails real em banco exclusivo e transporte em memória."""

import asyncio
import json
import os
from pathlib import Path

import httpx
import pytest

from app.database import connection, lock_contact
from app.recovery import import_one, reconcile_one
from app.security import encrypt
from app.services import projection, setup_account


@pytest.mark.skipif(
    not os.environ.get("PHASE2_CHATWOOT_DIR"), reason="Exige checkout Rails CE de teste"
)
async def test_phase2_real_rails(db):
    root = Path(__file__).resolve().parents[1]
    env = dict(os.environ)
    env.update(
        RAILS_ENV="test",
        DISABLE_ENTERPRISE="true",
        LOG_LEVEL="fatal",
        DATABASE_URL=os.environ["PHASE2_CHATWOOT_DATABASE"],
    )
    # Segredos transitam apenas pelos pipes do processo, nunca por arquivos/argv/logs.
    process = await asyncio.create_subprocess_exec(
        "bundle",
        "exec",
        "rails",
        "runner",
        str(root / "tests/contracts/phase2_bridge.rb"),
        cwd=os.environ["PHASE2_CHATWOOT_DIR"],
        env=env,
        stdin=asyncio.subprocess.PIPE,
        stdout=asyncio.subprocess.PIPE,
        stderr=asyncio.subprocess.DEVNULL,
    )

    async def receive():
        line = await asyncio.wait_for(process.stdout.readline(), 60)
        assert line, "Rails não iniciou a ponte isolada"
        return json.loads(line)

    try:
        fixture = await receive()
        account, contact = fixture["account"], fixture["contact"]

        class CW:
            async def request(self, method, path, **kwargs):
                process.stdin.write(
                    (
                        json.dumps({"method": method, "path": path, **kwargs}) + "\n"
                    ).encode()
                )
                await process.stdin.drain()
                response = await receive()
                if response["status"] >= 400:
                    raise httpx.HTTPStatusError(
                        "Falha no contrato Rails",
                        request=httpx.Request(method, "http://test"),
                        response=httpx.Response(response["status"]),
                    )
                return response["body"]

        cw = CW()
        cw.account = account
        async with connection() as conn:
            await conn.execute(
                "INSERT INTO kb_accounts(account_id,token_cipher) VALUES($1,$2)",
                account,
                encrypt("synthetic"),
            )
            await setup_account(conn, cw)
            await setup_account(conn, cw)
            assert (
                await conn.fetchval(
                    "SELECT count(*) FROM kb_resources WHERE account_id=$1", account
                )
                == 7
            )
            resources = await conn.fetch(
                "SELECT ownership FROM kb_resources WHERE account_id=$1", account
            )
            assert all(r["ownership"] == "created" for r in resources)
            result = await cw.request("GET", "/contacts", params={"page": 1})
            assert result["meta"]["count"] == 1
            await conn.execute(
                "UPDATE kb_accounts SET import_status='pending' WHERE account_id=$1",
                account,
            )
            assert await import_one(conn, cw)
            assert not await import_one(conn, cw)
            assert (
                await conn.fetchval(
                    "SELECT count(*) FROM kb_cards WHERE account_id=$1", account
                )
                == 0
            )
            stage = await conn.fetchrow(
                "SELECT id,funnel_id FROM kb_stages WHERE account_id=$1 ORDER BY "
                "position LIMIT 1",
                account,
            )
            async with conn.transaction():
                await lock_contact(conn, account, contact)
                await conn.execute(
                    "INSERT INTO "
                    "kb_cards(account_id,contact_id,funnel_id,stage_id) "
                    "VALUES($1,$2,$3,$4)",
                    account,
                    contact,
                    stage["funnel_id"],
                    stage["id"],
                )
            expected = await projection(conn, account, contact)
            await cw.request(
                "PATCH",
                f"/contacts/{contact}",
                json={"custom_attributes": {"kanban_etapa": "Divergente"}},
            )
            assert await reconcile_one(conn, cw)
            from app.worker import process_sync

            job = await conn.fetchrow(
                "SELECT * FROM kb_sync WHERE account_id=$1", account
            )
            await process_sync(conn, cw, job)
            updated = (await cw.request("GET", f"/contacts/{contact}"))["payload"]
            assert (
                updated["custom_attributes"]["kanban_etapa"] == expected["kanban_etapa"]
            )
            assert updated["custom_attributes"]["alheio"] == "preservar"
            assert updated["custom_attributes"]["origem"] == "Feira"
    finally:
        if process.returncode is None:
            process.stdin.write(b'{"stop":true}\n')
            await process.stdin.drain()
            await asyncio.wait_for(process.wait(), 15)
        assert process.returncode == 0, "Rails não concluiu rollback das fixtures"
