"""Regressões da indisponibilidade causada por contatos removidos no Chatwoot."""

from pathlib import Path

import httpx
import pytest

from app.database import connection
from app.recovery import reconcile_one
from app.worker import MAX_ATTEMPTS, heartbeat, process_delivery, process_sync


class Remote:
    account = 1

    def __init__(self, contact_status=404, account_status=200, patch_status=404):
        self.contact_status = contact_status
        self.account_status = account_status
        self.patch_status = patch_status
        self.calls = []

    async def request(self, method, path, **_kwargs):
        self.calls.append((method, path))
        status = self.patch_status if method == "PATCH" else self.contact_status
        if path == "/contacts":
            status = self.account_status
        if status != 200:
            request = httpx.Request(method, "http://test" + path)
            raise httpx.HTTPStatusError(
                "segredo", request=request, response=httpx.Response(status)
            )
        return {"payload": {"id": 10, "name": "Maria"}}


async def seed(conn, attempts=0):
    job = await conn.fetchrow(
        """INSERT INTO kb_sync(account_id,contact_id,attempts)
        VALUES(1,10,$1) RETURNING *""",
        attempts,
    )
    delivery = await conn.fetchrow(
        """INSERT INTO kb_deliveries(account_id,delivery_id,event_type,contact_id,
        payload,attempts) VALUES(1,'removed','contact_updated',10,'{}',$1)
        RETURNING *""",
        attempts,
    )
    await conn.execute(
        """INSERT INTO kb_tasks(account_id,contact_id,message,due_date)
        VALUES(1,10,'Ligar',current_date)"""
    )
    return job, delivery


@pytest.mark.parametrize("source", ["sync", "delivery", "reconcile"])
async def test_missing_contact_retires_atomically_and_isolates_account(db, source):
    remote = Remote()
    async with connection() as conn:
        job, delivery = await seed(conn)
        if source == "sync":
            await process_sync(conn, remote, job)
            assert remote.calls[:2] == [
                ("PATCH", "/contacts/10"),
                ("GET", "/contacts/10"),
            ]
        elif source == "delivery":
            await process_delivery(conn, remote, delivery)
        else:
            assert await reconcile_one(conn, remote)
        assert await conn.fetchval("SELECT status FROM kb_sync") == "gone"
        assert await conn.fetchval("SELECT status FROM kb_deliveries") == "gone"
        assert await conn.fetchval("SELECT status FROM kb_tasks") == "closed"
        assert (
            await conn.fetchval(
                "SELECT count(*) FROM kb_card_deletions WHERE account_id=1"
            )
            == 1
        )
        assert (
            await conn.fetchval(
                "SELECT count(*) FROM kb_card_deletions WHERE account_id=2"
            )
            == 0
        )
        before = len(remote.calls)
        await process_sync(conn, remote, job)
        await process_delivery(conn, remote, delivery)
        assert len(remote.calls) == before
        assert (
            await conn.fetchval(
                "SELECT count(*) FROM kb_history WHERE action='contato_removido'"
            )
            == 1
        )


@pytest.mark.parametrize(
    "contact_status,account_status", [(200, 200), (403, 200), (404, 404), (404, 401)]
)
async def test_unconfirmed_404_does_not_remove_cards(
    db, contact_status, account_status
):
    async with connection() as conn:
        job, _ = await seed(conn)
        await process_sync(conn, Remote(contact_status, account_status), job)
        assert await conn.fetchval("SELECT status FROM kb_sync") == "failed"
        assert await conn.fetchval("SELECT count(*) FROM kb_card_deletions") == 0
        assert await conn.fetchval("SELECT status FROM kb_tasks") == "active"


@pytest.mark.parametrize("source", ["sync", "delivery"])
@pytest.mark.parametrize("status", [401, 404, 429, 500])
async def test_retry_limit_is_terminal_and_can_be_retried(client, source, status):
    remote = Remote(status, status, status)
    async with connection() as conn:
        job, delivery = await seed(conn, MAX_ATTEMPTS - 1)
        if source == "sync":
            await process_sync(conn, remote, job)
            table = "kb_sync"
        else:
            await process_delivery(conn, remote, delivery)
            table = "kb_deliveries"
        assert await conn.fetchval(f"SELECT status FROM {table}") == "dead"
        assert await conn.fetchval(f"SELECT attempts FROM {table}") == MAX_ATTEMPTS
        await conn.execute("UPDATE kb_accounts SET remote_next_attempt=now()")
        before = len(remote.calls)
        if source == "sync":
            await process_sync(conn, remote, job)
        else:
            await process_delivery(conn, remote, delivery)
        assert len(remote.calls) == before
    assert (await client.post("/kanban/sync/retry")).status_code == 200
    async with connection() as conn:
        assert await conn.fetchval(f"SELECT attempts FROM {table}") == 0


async def test_container_liveness_independent_of_failed_queue(client):
    async with connection() as conn:
        await seed(conn)
        await heartbeat(conn)
        await conn.execute("UPDATE kb_sync SET status='dead'")
    assert (await client.get("/health")).status_code == 503
    assert (await client.get("/health/live")).status_code == 200
    assert (await client.get("/kanban/loader.js")).status_code == 200
    assert "8000/health/live'" in Path("Dockerfile").read_text()


async def test_cleanup_rolls_back_if_history_fails(db, monkeypatch):
    from app import services

    async def fail_record(*_args, **_kwargs):
        raise RuntimeError("Falha ao gravar histórico")

    monkeypatch.setattr(services, "record", fail_record)
    async with connection() as conn:
        job, _ = await seed(conn)
        await process_sync(conn, Remote(), job)
        assert await conn.fetchval("SELECT count(*) FROM kb_card_deletions") == 0
        assert await conn.fetchval("SELECT status FROM kb_tasks") == "active"
        assert await conn.fetchval("SELECT status FROM kb_deliveries") == "received"
        assert await conn.fetchval("SELECT status FROM kb_sync") == "failed"


async def test_missing_conversation_does_not_retire_contact(db, monkeypatch):
    from app import worker

    class ConversationRemote(Remote):
        async def request(self, method, path, **kwargs):
            if path.startswith("/conversations/"):
                raise httpx.HTTPStatusError(
                    "Ausente",
                    request=httpx.Request(method, "http://test"),
                    response=httpx.Response(404),
                )
            return await super().request(method, path, **kwargs)

    async def refresh(*_args, **_kwargs):
        return None

    monkeypatch.setattr(worker, "refresh_contact", refresh)
    async with connection() as conn:
        _, delivery = await seed(conn)
        await conn.execute(
            """UPDATE kb_deliveries SET event_type='conversation_created',
            payload='{"id":123}' WHERE id=$1""",
            delivery["id"],
        )
        await process_delivery(conn, ConversationRemote(200), delivery)
        assert await conn.fetchval("SELECT status FROM kb_deliveries") == "gone"
        assert await conn.fetchval("SELECT status FROM kb_tasks") == "active"
        assert await conn.fetchval("SELECT count(*) FROM kb_card_deletions") == 0
