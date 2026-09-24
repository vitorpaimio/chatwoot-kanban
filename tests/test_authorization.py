"""Provas negativas da política de caixas, conta e fluxo SSE."""

import asyncio
from types import SimpleNamespace

import httpx
import pytest
from fastapi import HTTPException

from app import security
from app.database import connection, notify, record
from app.events import hub
from app.main import app
from app.routers import workspace
from app.security import identity
from app.worker import tick

AGENT = {"account": 1, "id": 4, "name": "Agente", "role": "agent", "inboxes": [11]}
ADMIN = {"account": 1, "id": 3, "name": "Admin", "role": "administrator"}


async def seed():
    async with connection() as conn:
        original = await conn.fetchrow("SELECT * FROM kb_cards WHERE account_id=1")
        await conn.execute("""UPDATE kb_cards SET conversation_id=100,
            conversation_inbox_id=22,created_by=3 WHERE account_id=1""")
        await conn.execute("""UPDATE kb_contacts SET conversation_id=100,
            inbox_id=22 WHERE account_id=1 AND contact_id=10""")
        cards = {
            "hidden": original["id"],
            "stage": original["stage_id"],
            "funnel": original["funnel_id"],
        }
        for contact, name, creator, conversation, inbox in [
            (20, "VISIVEL", 3, 200, 11),
            (30, "CRIADOR", 4, None, None),
            (40, "SEM_CONVERSA_ALHEIO", 3, None, None),
        ]:
            await conn.execute(
                """INSERT INTO kb_contacts(account_id,contact_id,name,inbox_id)
                VALUES(1,$1,$2,$3)""",
                contact,
                name,
                inbox,
            )
            cid = await conn.fetchval(
                """INSERT INTO kb_cards(account_id,contact_id,
                funnel_id,stage_id,created_by,conversation_id,conversation_inbox_id)
                VALUES(1,$1,$2,$3,$4,$5,$6) RETURNING id""",
                contact,
                original["funnel_id"],
                original["stage_id"],
                creator,
                conversation,
                inbox,
            )
            cards[name] = cid
        for name, cid in [
            ("SEGREDO_CARD", original["id"]),
            ("VISIVEL", cards["VISIVEL"]),
        ]:
            contact = 10 if name == "SEGREDO_CARD" else 20
            await record(
                conn,
                1,
                contact,
                ADMIN,
                "cartao_movido",
                after={"card_id": cid, "marker": name},
                funnel=original["funnel_id"],
                stage=original["stage_id"],
                sync=False,
            )
    return cards


async def mock_cache(_conn, _account, key, _fetch):
    if key.startswith("options"):
        return {
            "inboxes": [
                {"id": 11, "name": "Permitida"},
                {"id": 22, "name": "CAIXA_SECRETA"},
            ],
            "agents": [],
        }
    if key == "conversations":
        return [
            {"id": 100, "contact_id": 10, "inbox_id": 22, "status": "open"},
            {"id": 200, "contact_id": 20, "inbox_id": 11, "status": "open"},
        ]
    return {"events": []}


@pytest.fixture
async def agent_client(client, monkeypatch):
    app.dependency_overrides[identity] = lambda: dict(AGENT)
    monkeypatch.setattr("app.metrics.service.cached", mock_cache)
    yield client
    await hub.close()


async def test_card_reads_writes_and_contact_task_scope(agent_client):
    cards = await seed()
    client = agent_client
    board = (await client.get("/kanban/board")).json()
    assert {c["id"] for c in board["cards"]} == {cards["VISIVEL"], cards["CRIADOR"]}
    assert board["contacts"] == []  # Catálogo pesquisado sob demanda.
    hidden, stage = cards["hidden"], cards["stage"]
    async with connection() as conn:
        foreign = await conn.fetchval("SELECT id FROM kb_cards WHERE account_id=2")
    for cid in (hidden, cards["SEM_CONVERSA_ALHEIO"], foreign, 999999999):
        assert (await client.get(f"/kanban/cards/{cid}")).status_code == 404
        for path, method, body in [
            (f"/cards/{cid}", "PATCH", {"version": 1, "stage_id": stage}),
            (
                f"/cards/{cid}/conversation",
                "PUT",
                {"version": 1, "conversation_id": 200},
            ),
        ]:
            response = await client.request(method, "/kanban" + path, json=body)
            assert response.status_code == 404
            assert response.json() == {"detail": "Registro não encontrado nesta conta"}
    assert (
        await client.patch(
            "/kanban/contacts/10/stage", json={"version": 1, "stage_id": stage}
        )
    ).status_code == 404
    assert (
        await client.patch(
            f"/kanban/cards/{cards['VISIVEL']}",
            json={"version": 1, "stage_id": stage, "before_id": hidden},
        )
    ).status_code == 404
    assert (
        await client.post(
            "/kanban/cards",
            json={"contact_id": 10, "funnel_id": cards["funnel"], "stage_id": stage},
        )
    ).status_code == 404
    assert (
        await client.put(
            "/kanban/contacts/10/task",
            json={"descricao": "Tarefa compartilhada", "vencimento": "2026-10-01"},
        )
    ).status_code == 200
    assert (await client.get("/kanban/contacts/10/task")).json()[
        "descricao"
    ] == "Tarefa compartilhada"
    assert (await client.get("/kanban/contacts/999999/task")).status_code == 404
    tasks = (await client.get("/kanban/metrics/tasks")).json()
    assert tasks["current"]["open"] == 1
    history = (await client.get("/kanban/history")).json()
    assert any(h["action"] == "tarefa_criada" for h in history)
    assert "SEGREDO_CARD" not in str(history)
    report = (await client.get("/kanban/reports")).json()
    assert sum(s["quantity"] for s in report["stages"]) == 2
    assert "SEGREDO_CARD" not in str(report)
    assert report["evolution"]["moves"] <= 1
    async with connection() as conn:
        assert (
            await conn.fetchval("SELECT version FROM kb_cards WHERE id=$1", hidden) == 1
        )


@pytest.mark.parametrize(
    "block",
    ["summary", "funnel", "losses", "sources", "team", "tasks", "timeline"],
)
@pytest.mark.parametrize("format", ["json", "csv"])
async def test_metrics_and_exports_exclude_hidden_cards(agent_client, block, format):
    cards = await seed()
    # Valores exclusivos do cartão oculto não podem entrar nas agregações.
    async with connection() as conn:
        stage = await conn.fetchval(
            "SELECT id FROM kb_stages WHERE account_id=1 AND kind='won'"
        )
        await conn.execute(
            """UPDATE kb_cards SET stage_id=$2,value_cents=987654321,
            source='SEGREDO_CARD',campaign='SEGREDO_CARD' WHERE id=$1""",
            cards["hidden"],
            stage,
        )
    result = await agent_client.get(f"/kanban/metrics/{block}?format={format}")
    assert result.status_code == 200, result.text
    assert "SEGREDO_CARD" not in result.text
    assert "987654321" not in result.text
    assert "CAIXA_SECRETA" not in result.text
    if block == "summary" and format == "json":
        assert result.json()["current"]["leads"] == 2
        assert result.json()["current"]["revenue"] == 0
    if block == "service" and format == "json":
        assert result.json()["current"]["open"] == 1
    forbidden = await agent_client.get(
        f"/kanban/metrics/{block}?format={format}&inbox_id=22"
    )
    assert forbidden.status_code == 404


async def test_options_exclude_forbidden_inbox(agent_client):
    result = await agent_client.get("/kanban/metrics/options")
    assert result.status_code == 200
    assert [i["id"] for i in result.json()["inboxes"]] == [11]


async def test_disabled_account_blocks_every_resource_and_worker(client, monkeypatch):
    cards = await seed()
    await client.put(
        "/kanban/contacts/10/task",
        json={"descricao": "Vencida", "vencimento": "2020-01-01"},
    )
    async with connection() as conn:
        await conn.execute("UPDATE kb_tasks SET due_state='active'")
        await conn.execute("""INSERT INTO
            kb_deliveries(account_id,delivery_id,event_type,
            contact_id,payload) VALUES(1,'disabled','contact_updated',10,'{}')""")
        await conn.execute(
            "UPDATE kb_accounts SET activation_status='pending' WHERE account_id=1"
        )
    assert (
        await client.put("/kanban/activation", json={"enabled": False})
    ).status_code == 200
    for path in [
        "board",
        "history",
        "reports",
        "events",
        "metrics/options",
        "metrics/configuration",
        "contacts/10/task",
        f"cards/{cards['hidden']}",
    ]:
        assert (await client.get("/kanban/" + path)).status_code == 403, path
    for block in [
        "summary",
        "funnel",
        "losses",
        "sources",
        "service",
        "team",
        "tasks",
        "timeline",
    ]:
        for format in ["json", "csv"]:
            assert (
                await client.get(f"/kanban/metrics/{block}?format={format}")
            ).status_code == 403
    for method, path, body in [
        (
            "PATCH",
            f"cards/{cards['hidden']}",
            {"version": 1, "stage_id": cards["stage"]},
        ),
        ("PUT", "contacts/10/task", {"descricao": "X", "vencimento": "2026-10-01"}),
        ("POST", "contacts/10/task/close", {"version": 1}),
        ("POST", "import", None),
        ("POST", "sync/retry", None),
    ]:
        assert (
            await client.request(method, "/kanban/" + path, json=body)
        ).status_code == 403

    async def forbidden(*_args, **_kwargs):
        pytest.fail("Worker de conta desativada acessou Chatwoot")

    monkeypatch.setattr("app.chatwoot_client.Chatwoot.request", forbidden)
    await tick()
    async with connection() as conn:
        assert (
            await conn.fetchval("SELECT due_state FROM kb_tasks WHERE account_id=1")
            == "active"
        )
        assert (
            await conn.fetchval("SELECT status FROM kb_deliveries WHERE account_id=1")
            == "received"
        )
        assert (
            await conn.fetchval("SELECT status FROM kb_sync WHERE account_id=1")
            == "pending"
        )
        assert (
            await conn.fetchval(
                "SELECT activation_status FROM kb_accounts WHERE account_id=1"
            )
            == "pending"
        )
    assert (
        await client.put("/kanban/activation", json={"enabled": True})
    ).status_code == 200
    # Habilitar não contorna um provisionamento ainda pendente.
    assert (await client.get("/kanban/board")).status_code == 403
    async with connection() as conn:
        await conn.execute(
            "UPDATE kb_accounts SET activation_status='ready' WHERE account_id=1"
        )
    assert (await client.get("/kanban/board")).status_code == 200


async def test_inbox_cache_ttl_closed_failure_and_session_isolation(monkeypatch):
    security._inbox_cache.clear()
    clock = [100.0]
    monkeypatch.setattr(security, "time", SimpleNamespace(monotonic=lambda: clock[0]))
    calls, payload, status = [], {"payload": [{"id": 11}]}, 200
    original = httpx.AsyncClient

    def respond(request):
        calls.append(request)
        assert "api_access_token" not in request.headers
        if status == 0:
            raise httpx.ReadTimeout("timeout")
        return httpx.Response(status, json=payload)

    monkeypatch.setattr(
        security.httpx,
        "AsyncClient",
        lambda **kw: original(transport=httpx.MockTransport(respond), **kw),
    )
    creds = {"access-token": "session-test", "client": "c", "uid": "u"}
    assert await security.allowed_inboxes(1, 4, creds) == [11]
    clock[0] = 159.99
    payload = {"payload": []}
    assert await security.allowed_inboxes(1, 4, creds) == [11]
    assert len(calls) == 1
    clock[0] = 160
    assert await security.allowed_inboxes(1, 4, creds) == []
    assert len(calls) == 2
    await security.allowed_inboxes(2, 4, creds)
    await security.allowed_inboxes(1, 5, creds)
    await security.allowed_inboxes(1, 4, {**creds, "access-token": "other-session"})
    assert len(calls) == 5
    for failure in (0, 500, 401):
        clock[0] += 61
        status = failure
        with pytest.raises(HTTPException) as exc:
            await security.allowed_inboxes(1, 4, creds)
        assert exc.value.status_code == 403
    status, payload = 200, {"payload": "invalid"}
    with pytest.raises(HTTPException):
        await security.allowed_inboxes(1, 4, creds)
    security._inbox_cache.clear()


async def test_sse_filters_hidden_changes_revokes_and_shares_listener(
    agent_client, monkeypatch
):
    cards = await seed()
    current = dict(AGENT)

    async def actor(_request):
        return current

    async def connected():
        return False

    monkeypatch.setattr(workspace, "identity", actor)
    request = SimpleNamespace(is_disconnected=connected)
    first = (await workspace.events(request, dict(AGENT))).body_iterator
    second = (await workspace.events(request, dict(AGENT))).body_iterator
    try:
        assert "ready" in await anext(first)
        listener = hub.connection
        assert "ready" in await anext(second)
        assert hub.connection is listener
        assert len(hub.subscribers["1"]) == 2
        waiting = asyncio.create_task(anext(first))
        async with connection() as conn:
            await conn.execute(
                "UPDATE kb_cards SET value_cents=100,version=version+1 WHERE id=$1",
                cards["hidden"],
            )
            await notify(conn, 1)
        await asyncio.sleep(0.03)
        assert not waiting.done()
        async with connection() as conn:
            await conn.execute(
                "UPDATE kb_cards SET value_cents=200,version=version+1 WHERE id=$1",
                cards["VISIVEL"],
            )
            await notify(conn, 1)
        assert "change" in await asyncio.wait_for(waiting, 1)
        current = {**AGENT, "inboxes": []}
        waiting = asyncio.create_task(anext(first))
        async with connection() as conn:
            await notify(conn, 1)
        assert "change" in await asyncio.wait_for(waiting, 1)
        async with connection() as conn:
            await conn.execute(
                "UPDATE kb_accounts SET enabled=false WHERE account_id=1"
            )
            await notify(conn, 1)
        assert "expired" in await asyncio.wait_for(anext(first), 1)
    finally:
        await first.aclose()
        await second.aclose()
        await hub.close()


async def test_conversation_recent_pin_and_cross_contact(agent_client, monkeypatch):
    from app.services import refresh_contact

    cards = await seed()
    conversations = [
        {"id": 200, "inbox_id": 11, "last_activity_at": 100},
        {"id": 201, "inbox_id": 11, "last_activity_at": 200},
        {"id": 202, "inbox_id": 22, "last_activity_at": 50},
    ]

    async def remote(_self, _method, path, **_kwargs):
        if path.endswith("/conversations"):
            return {"payload": conversations}
        if path.endswith("/labels"):
            return {"payload": []}
        return {"payload": {"id": 20, "name": "VISIVEL"}}

    monkeypatch.setattr("app.chatwoot_client.Chatwoot.request", remote)
    cid = cards["VISIVEL"]
    for other in (202, 99999):
        result = await agent_client.put(
            f"/kanban/cards/{cid}/conversation",
            json={"version": 1, "conversation_id": other},
        )
        assert result.status_code == 404
    assert (
        await agent_client.put(
            f"/kanban/cards/{cid}/conversation",
            json={"version": 1, "conversation_id": 200},
        )
    ).status_code == 200
    from app.chatwoot_client import Chatwoot

    async with connection() as conn, conn.transaction():
        async with await Chatwoot.for_account(conn, 1) as cw:
            await refresh_contact(conn, cw, 20)
        assert (
            await conn.fetchval("SELECT conversation_id FROM kb_cards WHERE id=$1", cid)
            == 200
        )
    assert (
        await agent_client.put(
            f"/kanban/cards/{cid}/conversation",
            json={"version": 2, "conversation_id": None},
        )
    ).status_code == 200
    row = (await agent_client.get(f"/kanban/cards/{cid}")).json()
    assert row["conversation_id"] == 201
    assert row["conversation_pinned"] is False
    async with connection() as conn, conn.transaction():
        conversations.clear()
        async with await Chatwoot.for_account(conn, 1) as cw:
            await refresh_contact(conn, cw, 20)
    # Creator is another user: without a conversation the agent now loses the card.
    assert (await agent_client.get(f"/kanban/cards/{cid}")).status_code == 404


async def test_development_migration_dry_run_conflict_and_repeat(db):
    from scripts.migrate_development_attributes import migrate

    async with connection() as conn:
        await conn.execute(
            """UPDATE kb_contacts SET remote_attributes=$1
            WHERE account_id=1 AND contact_id=10""",
            {
                "pipeline_01_etapas": "Novo",
                "kanban_view_mensaje": "Legado",
                "kanban_view_fecha_termino": "2026-10-01",
            },
        )
        report = await migrate(conn, 1)
        assert report[0]["status"] == "criar"
        assert not report[0]["aplicado"]
        assert await conn.fetchval("SELECT count(*) FROM kb_tasks") == 0
        await migrate(conn, 1, apply=True)
        assert await conn.fetchval("SELECT count(*) FROM kb_tasks") == 1
        assert await migrate(conn, 1, apply=True) == []
        await conn.execute(
            """UPDATE kb_contacts SET remote_attributes=$1
            WHERE account_id=1 AND contact_id=10""",
            {
                "kanban_view_mensaje": "Conflito",
                "kanban_view_fecha_termino": "2026-10-02",
            },
        )
        assert (await migrate(conn, 1, apply=True))[0]["status"] == "bloqueado"
        assert await conn.fetchval("SELECT message FROM kb_tasks") == "Legado"


@pytest.mark.parametrize(
    "path",
    [
        "board",
        "history",
        "reports",
        "events",
        "cards/1",
        "contacts/10/task",
        "metrics/options",
        "metrics/configuration",
        "metrics/summary?format=csv",
        "metrics/service?format=csv",
    ],
)
async def test_forged_account_denied_before_resource_lookup(client, monkeypatch, path):
    app.dependency_overrides.clear()
    original = httpx.AsyncClient

    def respond(_request):
        return httpx.Response(
            200,
            json={
                "id": 4,
                "name": "Agente",
                "accounts": [{"id": 1, "status": "active", "role": "agent"}],
            },
        )

    monkeypatch.setattr(
        security.httpx,
        "AsyncClient",
        lambda **kw: original(transport=httpx.MockTransport(respond), **kw),
    )
    separator = "&" if "?" in path else "?"
    result = await client.get(
        f"/kanban/{path}{separator}account=2",
        headers={"access-token": "session", "client": "test", "uid": "agent"},
    )
    assert result.status_code == 403
    assert result.json() == {"detail": "Conta não autorizada"}


async def test_sse_revalidates_at_permission_deadline_without_notification(
    agent_client, monkeypatch
):
    import time

    await seed()
    user = {**AGENT, "permission_deadline": time.monotonic() + 0.03}

    async def revoked(_request):
        return {**AGENT, "inboxes": []}

    async def connected():
        return False

    monkeypatch.setattr(workspace, "identity", revoked)
    stream = (
        await workspace.events(SimpleNamespace(is_disconnected=connected), user)
    ).body_iterator
    try:
        assert "ready" in await anext(stream)
        assert "change" in await asyncio.wait_for(anext(stream), 1)
    finally:
        await stream.aclose()
        await hub.close()


async def test_disable_waits_for_authorized_unit_and_rejects_webhook(client):
    from tests.test_workspace import signed

    async with connection(ADMIN):
        disable = asyncio.create_task(
            client.put("/kanban/activation", json={"enabled": False})
        )
        await asyncio.sleep(0.03)
        assert not disable.done()
    assert (await asyncio.wait_for(disable, 1)).status_code == 200
    body, headers = signed({"event": "contact_updated", "account": {"id": 1}, "id": 10})
    assert (
        await client.post("/kanban/webhooks/1/events", content=body, headers=headers)
    ).status_code == 401


async def test_activation_does_not_import_or_create_cards(client, monkeypatch):
    from app.services import setup_account

    requests = []

    class CW:
        account = 1

        async def request(self, method, path, **_kwargs):
            requests.append((method, path))
            if path == "/custom_attribute_definitions":
                if method == "POST":
                    return {"id": len(requests), **_kwargs["json"]}
                return []
            if path == "/webhooks" and method == "GET":
                return {"payload": {"webhooks": []}}
            if path == "/webhooks":
                return {
                    "payload": {"webhook": {"id": 1, "secret": "synthetic-test-secret"}}
                }
            if path == "/dashboard_apps":
                return []
            pytest.fail("Ativação importou dados sem solicitação")

    async with connection() as conn:
        before = await conn.fetchval("SELECT count(*) FROM kb_cards")
        await setup_account(conn, CW())
        assert await conn.fetchval("SELECT count(*) FROM kb_cards") == before
        assert (
            await conn.fetchval(
                "SELECT activation_status FROM kb_accounts WHERE account_id=1"
            )
            == "ready"
        )
    assert all(not p.startswith("/contacts") for _, p in requests)


async def test_same_contact_history_is_scoped_to_card(agent_client):
    cards = await seed()
    async with connection() as conn:
        visible = await conn.fetchval(
            """INSERT INTO kb_cards
            (account_id,contact_id,funnel_id,stage_id,created_by,
             conversation_id,conversation_inbox_id)
            VALUES(1,10,$1,$2,4,201,11) RETURNING id""",
            cards["funnel"],
            cards["stage"],
        )
        await record(
            conn,
            1,
            10,
            ADMIN,
            "cartao_criado",
            after={"card_id": visible, "marker": "SEGUNDA_VISIVEL"},
            funnel=cards["funnel"],
            sync=False,
        )
    history = (await agent_client.get("/kanban/history")).json()
    assert "SEGUNDA_VISIVEL" in str(history)
    assert "SEGREDO_CARD" not in str(history)
    assert (
        await agent_client.get(f"/kanban/cards/{cards['hidden']}/conversations")
    ).status_code == 404


async def test_conversation_options_filter_inboxes(agent_client, monkeypatch):
    cards = await seed()

    async def remote(_self, _method, path, **_kwargs):
        assert path == "/contacts/20/conversations"
        return {
            "payload": [
                {
                    "id": 200,
                    "inbox_id": 11,
                    "status": "open",
                    "messages": [{"content": "Proposta autorizada"}],
                },
                {
                    "id": 202,
                    "inbox_id": 22,
                    "status": "open",
                    "messages": [{"content": "SEGREDO"}],
                },
            ]
        }

    monkeypatch.setattr("app.chatwoot_client.Chatwoot.request", remote)
    response = await agent_client.get(f"/kanban/cards/{cards['VISIVEL']}/conversations")
    assert response.status_code == 200
    assert [c["id"] for c in response.json()] == [200]
    assert "SEGREDO" not in response.text


async def test_deletion_rejects_inaccessible_cards(agent_client):
    cards = await seed()
    for cid in (cards["hidden"], cards["SEM_CONVERSA_ALHEIO"], 99999999):
        for path, method in (
            (f"/kanban/cards/{cid}", "DELETE"),
            (f"/kanban/cards/{cid}/restore", "POST"),
        ):
            response = await agent_client.request(method, path, json={"version": 1})
            assert response.status_code == 404
    response = await agent_client.request(
        "DELETE", f"/kanban/cards/{cards['VISIVEL']}", json={"version": 1}
    )
    assert response.status_code == 200
