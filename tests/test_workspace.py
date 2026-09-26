import asyncio
import hashlib
import hmac
import json
import time
from datetime import date

import asyncpg
import httpx
import pytest
from starlette.requests import Request

from app.database import connection, lock_contact, record
from app.main import app
from app.routers.workspace import Move, move_card
from app.security import identity
from app.services import SYSTEM, projection, refresh_contact, task_state
from app.worker import tick


async def board(client):
    response = await client.get("/kanban/board?account=1")
    assert response.status_code == 200, response.text
    return response.json()


async def test_board_is_read_only_and_isolated(client):
    first = await board(client)
    second = await board(client)
    assert first == second
    assert len(first["cards"]) == 1
    assert all(c["account_id"] == 1 for c in first["cards"])
    async with connection() as conn:
        assert await conn.fetchval("SELECT count(*) FROM kb_history") == 0
        assert await conn.fetchval("SELECT count(*) FROM kb_sync") == 0


async def test_moves_version_and_cross_account(client):
    data = await board(client)
    card = data["cards"][0]
    body = {"version": 1, "stage_id": data["stages"][1]["id"]}
    assert (
        await client.patch(f"/kanban/cards/{card['id']}", json=body)
    ).status_code == 200
    assert (
        await client.patch(f"/kanban/cards/{card['id']}", json=body)
    ).status_code == 409
    async with connection() as conn:
        other = await conn.fetchval("SELECT id FROM kb_cards WHERE account_id=2")
        assert (
            await client.patch(f"/kanban/cards/{other}", json=body)
        ).status_code == 404
        assert (
            await conn.fetchval("SELECT count(*) FROM kb_history WHERE account_id=1")
            == 1
        )
        assert (
            await conn.fetchval("SELECT version FROM kb_sync WHERE account_id=1") == 1
        )


async def test_task_close_recreate_and_projection(client):
    body = {"descricao": "Primeira", "vencimento": "2026-09-23"}
    assert (await client.put("/kanban/contacts/10/task", json=body)).status_code == 200
    assert (await client.put("/kanban/contacts/10/task", json=body)).status_code == 409
    assert (
        await client.post("/kanban/contacts/10/task/close", json={"version": 1})
    ).status_code == 200
    async with connection() as conn:
        attrs = await projection(conn, 1, 10)
        assert attrs["kanban_tarefa"] is None
        assert attrs["kanban_tarefa_vencimento"] is None
    body["descricao"] = "Segunda"
    assert (await client.put("/kanban/contacts/10/task", json=body)).status_code == 200
    async with connection() as conn:
        rows = await conn.fetch("SELECT * FROM kb_tasks ORDER BY id")
        assert [r["status"] for r in rows] == ["closed", "active"]
        assert rows[0]["closed_by"] == 3 and rows[1]["created_by"] == 3


async def test_multiple_funnels_and_legacy_ambiguity(client):
    fid = (await client.post("/kanban/funnels", json={"name": "Renovação"})).json()[
        "id"
    ]
    data = await board(client)
    stage = next(s for s in data["stages"] if s["funnel_id"] == fid)
    body = {"contact_id": 10, "funnel_id": fid, "stage_id": stage["id"]}
    assert (await client.post("/kanban/cards", json=body)).status_code == 200
    assert (
        await client.patch(
            "/kanban/contacts/10/stage", json={"version": 1, "stage_id": stage["id"]}
        )
    ).status_code == 409
    assert (
        await client.patch(
            f"/kanban/contacts/10/stage?funnel_id={fid}",
            json={"version": 1, "stage_id": stage["id"]},
        )
    ).status_code == 200
    async with connection() as conn:
        attrs = await projection(conn, 1, 10)
        assert "pipeline_01_etapas" not in attrs
        assert attrs["kanban_etapa"] == "Renovação / Novo"


async def test_archive_requires_destination_and_preserves(client):
    data = await board(client)
    stage = data["stages"][0]
    response = await client.post(f"/kanban/stages/{stage['id']}/archive", json={})
    assert response.status_code in (404, 409)
    response = await client.post(
        f"/kanban/stages/{stage['id']}/archive",
        json={"destination_id": data["stages"][1]["id"]},
    )
    assert response.status_code == 200, response.text
    async with connection() as conn:
        assert await conn.fetchval(
            "SELECT archived FROM kb_stages WHERE id=$1", stage["id"]
        )
        assert (
            await conn.fetchval("SELECT count(*) FROM kb_cards WHERE account_id=1") == 1
        )
        assert (
            await conn.fetchval("SELECT count(*) FROM kb_history WHERE account_id=1")
            == 2
        )


async def test_agent_permissions(client):
    app.dependency_overrides[identity] = lambda: {
        "account": 1,
        "id": 4,
        "name": "Agente",
        "role": "agent",
    }
    assert (
        await client.post("/kanban/funnels", json={"name": "Proibido"})
    ).status_code == 403
    assert (await client.post("/kanban/import")).status_code == 403
    assert (await client.post("/kanban/sync/retry")).status_code == 403
    assert (
        await client.put(
            "/kanban/contacts/10/task",
            json={"descricao": "Permitida", "vencimento": "2026-09-23"},
        )
    ).status_code == 200


def signed(payload, delivery="delivery-1", timestamp=None):
    raw = json.dumps(payload).encode()
    timestamp = timestamp or str(int(time.time()))
    sig = hmac.new(
        b"webhook-secret", timestamp.encode() + b"." + raw, hashlib.sha256
    ).hexdigest()
    return raw, {
        "x-chatwoot-timestamp": timestamp,
        "x-chatwoot-delivery": delivery,
        "x-chatwoot-signature": "sha256=" + sig,
    }


async def test_webhook_signature_dedup_and_account(client):
    payload = {"event": "contact_updated", "account": {"id": 1}, "id": 10}
    raw, headers = signed(payload)
    for _ in range(2):
        assert (
            await client.post("/kanban/webhooks/1/events", content=raw, headers=headers)
        ).status_code == 200
    async with connection() as conn:
        assert await conn.fetchval("SELECT count(*) FROM kb_deliveries") == 1
        assert await conn.fetchval("SELECT status FROM kb_deliveries") == "received"
    assert (
        await client.post("/kanban/webhooks/2/events", content=raw, headers=headers)
    ).status_code == 403
    assert (
        await client.post(
            "/kanban/webhooks/1/events", content=raw + b" ", headers=headers
        )
    ).status_code == 401
    raw, headers = signed(payload, timestamp="1")
    assert (
        await client.post("/kanban/webhooks/1/events", content=raw, headers=headers)
    ).status_code == 401


async def test_concurrency_and_atomicity(client):
    data = await board(client)
    card = data["cards"][0]
    stage = data["stages"][1]["id"]

    async def change():
        async with (
            connection({"account": 1, "id": 3, "role": "administrator"}) as conn,
            conn.transaction(),
        ):
            try:
                await move_card(
                    conn,
                    card["id"],
                    Move(version=1, stage_id=stage),
                    {"account": 1, "id": 3, "name": "A"},
                )
                return 200
            except Exception as error:
                return error.status_code

    assert sorted(await asyncio.gather(change(), change())) == [200, 409]
    async with connection() as conn:
        assert (
            await conn.fetchval("SELECT count(*) FROM kb_history WHERE account_id=1")
            == 1
        )
        with pytest.raises(RuntimeError):
            async with conn.transaction():
                await record(conn, 1, 10, SYSTEM, "deve_reverter")
                raise RuntimeError()
        assert not await conn.fetchval(
            "SELECT 1 FROM kb_history WHERE action='deve_reverter'"
        )


async def test_composite_foreign_keys(db):
    async with connection() as conn:
        stage = await conn.fetchval(
            "SELECT id FROM kb_stages WHERE account_id=2 LIMIT 1"
        )
        with pytest.raises(asyncpg.ForeignKeyViolationError):
            await conn.execute(
                "UPDATE kb_cards SET stage_id=$1 WHERE account_id=1", stage
            )


def test_due_today_is_not_overdue():
    assert task_state(date(2026, 9, 23), date(2026, 9, 23)) == "today"
    assert task_state(date(2026, 9, 23), date(2026, 9, 24)) == "overdue"
    assert task_state(date(2026, 9, 24), date(2026, 9, 23)) == "active"


async def test_history_by_contact(client):
    data = await board(client)
    card = data["cards"][0]
    await client.patch(
        f"/kanban/cards/{card['id']}",
        json={"version": 1, "stage_id": data["stages"][1]["id"], "value_cents": 12345},
    )
    assert (await client.get("/kanban/history?contact_id=999")).json() == []
    assert len((await client.get("/kanban/history?contact_id=10")).json()) == 1


async def test_worker_retries_latest_projection(client, monkeypatch):
    from app.chatwoot_client import Chatwoot

    sent = []

    async def request(_self, _method, _path, **kwargs):
        if not sent:
            sent.append("failure")
            raise httpx.ConnectError("offline")
        sent.append(kwargs["json"]["custom_attributes"])
        return {}

    monkeypatch.setattr(Chatwoot, "request", request)
    data = await board(client)
    card = data["cards"][0]
    await client.patch(
        f"/kanban/cards/{card['id']}",
        json={"version": 1, "stage_id": data["stages"][1]["id"]},
    )
    await tick()
    async with connection() as conn:
        assert (
            await conn.fetchval("SELECT status FROM kb_sync WHERE account_id=1")
            == "failed"
        )
    await client.patch(
        f"/kanban/cards/{card['id']}",
        json={
            "version": 2,
            "stage_id": data["stages"][2]["id"],
            "lost_reason": "Preço",
        },
    )
    await tick()
    assert sent[-1]["kanban_etapa"] == "Principal / Perdido"
    async with connection() as conn:
        row = await conn.fetchrow("SELECT * FROM kb_sync WHERE account_id=1")
        assert row["synced_version"] == row["version"] == 2
        assert row["status"] == "synced"


async def test_external_clear_and_pending_protection(client):
    class CW:
        account = 1
        attributes = {"kanban_etapa": "Principal / Ganho"}

        async def request(self, _method, path):
            if path.endswith("conversations"):
                return {"payload": []}
            if path.endswith("/labels"):
                return {"payload": ["VIP"]}
            return {
                "payload": {
                    "id": 10,
                    "name": "Atualizado",
                    "custom_attributes": self.attributes,
                }
            }

    cw = CW()
    await client.put(
        "/kanban/contacts/10/task",
        json={"descricao": "Local", "vencimento": "2026-09-23"},
    )
    async with connection() as conn, conn.transaction():
        await lock_contact(conn, 1, 10)
        await refresh_contact(conn, cw, 10)
        assert await conn.fetchval(
            "SELECT labels FROM kb_contacts WHERE account_id=1"
        ) == ["VIP"]
        assert (
            await conn.fetchval("SELECT message FROM kb_tasks WHERE status='active'")
            == "Local"
        )
        assert (
            await conn.fetchval(
                "SELECT count(*) FROM kb_history WHERE action='espelho_divergente'"
            )
            == 1
        )
        await conn.execute("UPDATE kb_sync SET status='synced'")
        await conn.execute(
            "UPDATE kb_contacts SET remote_attributes=$1 WHERE account_id=1",
            {"kanban_tarefa": "Local", "kanban_tarefa_vencimento": "2026-09-23"},
        )
        cw.attributes = {}
        await refresh_contact(conn, cw, 10)
        assert (
            await conn.fetchval("SELECT count(*) FROM kb_tasks WHERE status='active'")
            == 1
        )


async def test_real_auth_contract(db, monkeypatch):
    from app import security

    original = httpx.AsyncClient
    profile = {
        "id": 3,
        "name": "Admin",
        "accounts": [{"id": 1, "status": "active", "role": "administrator"}],
    }
    response_status = 200

    def respond(request):
        return httpx.Response(response_status, json=profile)

    monkeypatch.setattr(
        security.httpx,
        "AsyncClient",
        lambda **kw: original(transport=httpx.MockTransport(respond), **kw),
    )

    def req(account=1, headers=None):
        return Request(
            {
                "type": "http",
                "method": "GET",
                "query_string": f"account={account}".encode(),
                "headers": headers or [],
            }
        )

    from fastapi import HTTPException

    with pytest.raises(HTTPException) as error:
        await identity(req())
    assert error.value.status_code == 401
    headers = [(b"access-token", b"valid"), (b"uid", b"user"), (b"client", b"client")]
    assert (await identity(req(headers=headers)))["account"] == 1
    with pytest.raises(HTTPException) as error:
        await identity(req(2, headers))
    assert error.value.status_code == 403
    response_status = 401
    # Sessão válida fica em cache pelo prazo configurado; depois é revalidada.
    assert (await identity(req(headers=headers)))["account"] == 1
    security._profile_cache.clear()
    with pytest.raises(HTTPException) as error:
        await identity(req(headers=headers))
    assert error.value.status_code == 401
    response_status = 200
    assert (await identity(req(headers=headers)))["account"] == 1
    monkeypatch.setattr(security.settings, "session_cache_seconds", 0)
    security._profile_cache.clear()
    await identity(req(headers=headers))
    response_status = 401
    with pytest.raises(HTTPException) as error:
        await identity(req(headers=headers))
    assert error.value.status_code == 401


async def test_closed_public_proxy_routes(client):
    assert (await client.get("/api/contacts")).status_code == 404
    assert (await client.get("/kanban/debug/raw")).status_code == 404
    assert (await client.get("/kanban/cron")).status_code == 404


async def test_sse_account_signal_and_expiration(db, monkeypatch):
    from fastapi import HTTPException

    from app.config import settings
    from app.routers import workspace

    async def receive():
        await asyncio.sleep(60)
        return {"type": "http.disconnect"}

    request = Request(
        {"type": "http", "method": "GET", "headers": [], "query_string": b"account=1"},
        receive=receive,
    )
    user = {"account": 1, "id": 3, "role": "administrator"}

    async def valid(_request):
        return user

    monkeypatch.setattr(workspace, "identity", valid)
    response = await workspace.events(request, user)
    stream = response.body_iterator
    assert "ready" in await anext(stream)
    waiting = asyncio.create_task(anext(stream))
    async with connection() as conn:
        await conn.execute("SELECT pg_notify('kanban_events','2')")
    await asyncio.sleep(0.03)
    assert not waiting.done()
    async with connection() as conn:
        await conn.execute("SELECT pg_notify('kanban_events','1')")
    await asyncio.sleep(0.03)
    assert not waiting.done()
    async with connection() as conn:
        await conn.execute("UPDATE kb_cards SET version=version+1 WHERE account_id=1")
        await conn.execute("SELECT pg_notify('kanban_events','1')")
    assert "change" in await asyncio.wait_for(waiting, 1)
    monkeypatch.setattr(settings, "session_recheck_seconds", -1)

    async def expired(_request):
        raise HTTPException(401)

    monkeypatch.setattr(workspace, "identity", expired)
    waiting = asyncio.create_task(anext(stream))
    async with connection() as conn:
        await conn.execute("SELECT pg_notify('kanban_events','1')")
    assert "expired" in await asyncio.wait_for(waiting, 1)
    await stream.aclose()
    await workspace.hub.close()


async def test_cookie_origin_and_suspended_account(db, monkeypatch):
    from urllib.parse import quote

    from fastapi import HTTPException

    from app import security

    original = httpx.AsyncClient
    profile = {
        "id": 3,
        "name": "A",
        "accounts": [{"id": 1, "status": "suspended", "role": "administrator"}],
    }
    monkeypatch.setattr(
        security.httpx,
        "AsyncClient",
        lambda **kw: original(
            transport=httpx.MockTransport(lambda _r: httpx.Response(200, json=profile)),
            **kw,
        ),
    )
    cookie = "cw_d_session_info=" + quote(
        json.dumps({"access-token": "value", "client": "client", "uid": "user"})
    )
    scope = {
        "type": "http",
        "method": "POST",
        "query_string": b"account=1",
        "headers": [(b"cookie", cookie.encode()), (b"origin", b"https://evil.test")],
    }
    with pytest.raises(HTTPException) as error:
        await identity(Request(scope))
    assert error.value.status_code == 403
    scope["headers"] = [(b"cookie", cookie.encode())]
    with pytest.raises(HTTPException) as error:
        await identity(Request(scope))
    assert error.value.status_code == 403


async def test_positions_rebalance_and_duplicate_stage(client):
    data = await board(client)
    card = data["cards"][0]
    stage = data["stages"][0]
    async with connection() as conn:
        for contact in (11, 12):
            await conn.execute(
                """INSERT INTO kb_contacts(account_id,contact_id,name)
                VALUES(1,$1,'Ordenação')""",
                contact,
            )
            await conn.execute(
                """INSERT INTO kb_cards(account_id,contact_id,
                funnel_id,stage_id,position) VALUES(1,$1,$2,$3,$4)""",
                contact,
                card["funnel_id"],
                stage["id"],
                "1.00000000001" if contact == 12 else "1",
            )
        before = await conn.fetchval(
            "SELECT id FROM kb_cards WHERE account_id=1 AND contact_id=12"
        )
    response = await client.patch(
        f"/kanban/cards/{card['id']}",
        json={"version": 1, "stage_id": stage["id"], "before_id": before},
    )
    assert response.status_code == 200, response.text
    async with connection() as conn:
        ordered = await conn.fetch("""SELECT contact_id FROM kb_cards
            WHERE account_id=1 ORDER BY position,id""")
    assert [r["contact_id"] for r in ordered] == [11, 10, 12]
    duplicate = await client.post(
        f"/kanban/funnels/{card['funnel_id']}/stages", json={"name": " novo "}
    )
    assert duplicate.status_code == 409


async def test_import_waits_for_stage_archive_lock(client):
    from app.database import lock_primary_contact

    data = await board(client)
    stage = data["stages"][0]
    acquired = asyncio.Event()

    async def importer():
        async with connection() as conn, conn.transaction():
            await lock_primary_contact(conn, 1, 10)
            acquired.set()
            active = await conn.fetchval(
                "SELECT NOT archived FROM kb_stages WHERE id=$1", stage["id"]
            )
            return active

    async with connection() as conn, conn.transaction():
        await conn.execute(
            "SELECT id FROM kb_funnels WHERE id=$1 FOR UPDATE", stage["funnel_id"]
        )
        waiting = asyncio.create_task(importer())
        await asyncio.sleep(0.03)
        assert not acquired.is_set()
        await conn.execute(
            "UPDATE kb_stages SET archived=true WHERE id=$1", stage["id"]
        )
    assert await asyncio.wait_for(waiting, 1) is False


async def test_new_deal_imports_selected_contact_only(client, monkeypatch):
    from app.chatwoot_client import Chatwoot

    async def request(self, method, path, **kwargs):
        assert self.account == 1 and method == "GET"
        if path == "/contacts/99":
            return {"payload": {"id": 99, "name": "Contato remoto"}}
        if path in ("/contacts/99/conversations", "/contacts/99/labels"):
            return {"payload": []}
        raise httpx.HTTPStatusError(
            "not found",
            request=httpx.Request("GET", "http://test"),
            response=httpx.Response(404),
        )

    monkeypatch.setattr(Chatwoot, "request", request)
    data = await board(client)
    body = {
        "contact_id": 99,
        "funnel_id": data["funnels"][0]["id"],
        "stage_id": data["stages"][1]["id"],
    }
    response = await client.post("/kanban/cards", json=body)
    assert response.status_code == 200, response.text
    async with connection() as conn:
        cards = await conn.fetch("SELECT * FROM kb_cards WHERE contact_id=99")
        assert len(cards) == 1 and cards[0]["stage_id"] == body["stage_id"]
        assert (
            await conn.fetchval("SELECT count(*) FROM kb_history WHERE contact_id=99")
            == 1
        )
    body["contact_id"] = 100
    assert (await client.post("/kanban/cards", json=body)).status_code == 404


async def test_remove_only_owned_conversation_app(client, monkeypatch):
    from app.chatwoot_client import Chatwoot
    from app.config import settings
    from app.services import remove_conversation_app

    removed = []
    apps = [
        {
            "id": 1,
            "title": "Kanban",
            "content": [{"url": f"{settings.public_url}/kanban/?account=1&compact=1"}],
        },
        {"id": 2, "title": "Kanban", "content": [{"url": "https://other.example/app"}]},
        {"id": 3, "title": "Outro", "content": []},
    ]

    async def request(self, method, path, **kwargs):
        if method == "GET":
            return {"payload": [item for item in apps if item["id"] not in removed]}
        assert method == "DELETE"
        removed.append(int(path.rsplit("/", 1)[1]))
        return {}

    monkeypatch.setattr(Chatwoot, "request", request)
    async with connection() as conn, Chatwoot(1, "token") as cw:
        await remove_conversation_app(conn, cw)
        await remove_conversation_app(conn, cw)
    assert removed == [1]


async def test_multiple_deals_same_funnel_move_independently(client):
    data = await board(client)
    original = data["cards"][0]
    body = {
        "contact_id": 10,
        "funnel_id": original["funnel_id"],
        "stage_id": original["stage_id"],
    }
    response = await client.post("/kanban/cards", json=body)
    assert response.status_code == 200
    second = response.json()["id"]
    assert second != original["id"]
    moved = await client.patch(
        f"/kanban/cards/{second}",
        json={
            "version": 1,
            "stage_id": data["stages"][1]["id"],
            "value_cents": 123456,
        },
    )
    assert moved.status_code == 200
    cards = (await board(client))["cards"]
    assert len(cards) == 2
    assert (
        next(c for c in cards if c["id"] == original["id"])["stage_id"]
        == original["stage_id"]
    )
    assert (
        await client.put(
            "/kanban/contacts/10/task",
            json={
                "descricao": "Retorno compartilhado",
                "vencimento": "2026-10-07",
            },
        )
    ).status_code == 200
    cards = (await board(client))["cards"]
    assert cards[0]["task_id"] == cards[1]["task_id"]
    assert (
        await client.patch(
            f"/kanban/contacts/10/stage?funnel_id={original['funnel_id']}",
            json={"version": 1, "stage_id": original["stage_id"]},
        )
    ).status_code == 409
    assert (
        await client.patch(
            f"/kanban/cards/{second}",
            json={
                "version": 2,
                "stage_id": data["stages"][1]["id"],
                "value_cents": 100_000_000_000,
            },
        )
    ).status_code == 422


async def test_delete_restore_preserves_contact_task_and_audit(client):
    data = await board(client)
    card = data["cards"][0]
    await client.put(
        "/kanban/contacts/10/task",
        json={"descricao": "Preservar tarefa", "vencimento": "2026-10-07"},
    )
    url = f"/kanban/cards/{card['id']}"
    assert (await client.delete(url, params={"account": 2})).status_code != 200
    result = await client.request("DELETE", url, json={"version": card["version"]})
    assert result.status_code == 200
    assert (await board(client))["cards"] == []
    assert (await client.get(url)).status_code == 404
    assert (await client.get("/kanban/contacts/10/task")).json()[
        "descricao"
    ] == "Preservar tarefa"
    async with connection() as conn:
        assert (
            await conn.fetchval("SELECT count(*) FROM kb_contacts WHERE account_id=1")
            == 1
        )
        assert (await projection(conn, 1, 10))["kanban_etapa"] is None
        assert (
            await conn.fetchval(
                "SELECT count(*) FROM kb_history WHERE action='negociacao_excluida'"
            )
            == 1
        )
        assert (
            await conn.fetchval("SELECT count(*) FROM kb_sync WHERE account_id=1") == 1
        )
    assert (
        await client.post(url + "/restore", json={"version": card["version"]})
    ).status_code == 409
    assert (await client.post(url + "/restore", json=result.json())).status_code == 200
    assert len((await board(client))["cards"]) == 1
