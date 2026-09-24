"""Provas transacionais da Fase 2 no PostgreSQL exclusivo."""

import httpx
import pytest

from app.chatwoot_client import Chatwoot, failure
from app.database import connection, lock_contact
from app.provisioning.attributes import provision_attributes
from app.recovery import import_one, reconcile_one
from app.services import projection, refresh_contact, setup_account
from app.worker import tick


class Remote:
    def __init__(self, account=1):
        self.account = account
        self.definitions = []
        self.hooks = []
        self.contacts = {10: {"id": 10, "name": "Maria", "custom_attributes": {}}}
        self.calls = []
        self.fail_key = None
        self.fail_contact = None

    async def request(self, method, path, **kwargs):
        self.calls.append((method, path, kwargs))
        if path == "/custom_attribute_definitions":
            if method == "GET":
                return self.definitions.copy()
            payload = kwargs["json"]
            if payload["attribute_key"] == self.fail_key:
                raise httpx.ConnectError("segredo-nunca-exibir")
            resource = {"id": len(self.definitions) + 1, **payload}
            self.definitions.append(resource)
            return resource
        if path == "/webhooks":
            if method == "GET":
                return {"payload": {"webhooks": self.hooks}}
            resource = {
                "id": 30,
                "secret": "segredo-nunca-exibir",
                **kwargs["json"]["webhook"],
            }
            self.hooks.append(resource)
            return {"payload": {"webhook": resource}}
        if path == "/dashboard_apps":
            return []
        if path == "/contacts":
            return {
                "meta": {"count": len(self.contacts)},
                "payload": list(self.contacts.values())
                if kwargs["params"]["page"] == 1
                else [],
            }
        contact_id = int(path.split("/")[2])
        if contact_id == self.fail_contact:
            raise httpx.ConnectError("offline")
        if path.endswith("/conversations"):
            return {"payload": []}
        if path.endswith("/labels"):
            return {"payload": []}
        if contact_id not in self.contacts:
            raise httpx.HTTPStatusError(
                "segredo-nunca-exibir",
                request=httpx.Request(method, "http://example.test"),
                response=httpx.Response(404),
            )
        if method == "PATCH":
            self.contacts[contact_id]["custom_attributes"].update(
                kwargs["json"]["custom_attributes"]
            )
        return {"payload": self.contacts[contact_id]}


async def test_manifest_survives_partial_failure_and_isolates_accounts(db):
    remote = Remote()
    remote.fail_key = "kanban_tarefa"
    async with connection() as conn:
        with pytest.raises(httpx.ConnectError):
            await setup_account(conn, remote)
        assert await conn.fetchval("SELECT count(*) FROM kb_resources") == 1
        remote.fail_key = None
        await setup_account(conn, remote)
        await setup_account(conn, remote)
        rows = await conn.fetch("SELECT * FROM kb_resources WHERE account_id=1")
        assert len(rows) == 7
        assert all(r["ownership"] == "created" for r in rows)
        assert "segredo-nunca-exibir" not in str(rows)
        assert (
            await conn.fetchval("SELECT count(*) FROM kb_resources WHERE account_id=2")
            == 0
        )
        assert len(remote.definitions) == 6


async def test_conflicts_disable_optional_and_block_required_before_writes(db):
    remote = Remote()
    remote.definitions = [
        {
            "id": 100,
            "attribute_key": "origem",
            "attribute_model": 1,
            "attribute_display_type": "number",
        }
    ]
    async with connection() as conn:
        await provision_attributes(conn, remote)
        row = await conn.fetchrow("SELECT * FROM kb_accounts WHERE account_id=1")
        assert row["attribute_mappings"]["origem"] is None
        assert "origem" not in [d["attribute_key"] for d in remote.definitions[1:]]
        assert row["provisioning_warnings"]
        assert remote.definitions[0]["attribute_display_type"] == "number"
        remote.definitions[1]["attribute_display_type"] = "number"
        before = len(remote.calls)
        from app.provisioning.attributes import AttributeConflictError

        with pytest.raises(AttributeConflictError):
            await provision_attributes(conn, remote)
        assert [c[0] for c in remote.calls[before:]] == ["GET"]


async def test_mapped_dimensions_import_snapshot_metrics_and_disabled(db):
    remote = Remote()
    remote.contacts[10]["custom_attributes"] = {"fonte": "Feira", "origem": "Ignorar"}
    async with connection() as conn:
        await conn.execute(
            "UPDATE kb_accounts SET attribute_mappings=$1 WHERE account_id=1",
            {"origem": "fonte", "campanha": None, "temperatura": None},
        )
        async with conn.transaction():
            await lock_contact(conn, 1, 10)
            await refresh_contact(conn, remote, 10)
        assert (
            await conn.fetchval("SELECT source FROM kb_cards WHERE account_id=1")
            == "Feira"
        )
        assert (
            await conn.fetchval(
                "SELECT source FROM kb_card_events WHERE account_id=1 ORDER BY id "
                "DESC LIMIT 1"
            )
            == "Feira"
        )
        assert (
            await conn.fetchval("SELECT source FROM kb_cards WHERE account_id=2")
            is None
        )
        await conn.execute(
            "UPDATE kb_accounts SET attribute_mappings='{}' WHERE account_id=1"
        )
        async with conn.transaction():
            await lock_contact(conn, 1, 10)
            await refresh_contact(conn, remote, 10)
        assert (
            await conn.fetchval("SELECT source FROM kb_cards WHERE account_id=1")
            is None
        )


async def test_estimate_separate_import_resume_no_duplicate_cards(client, monkeypatch):
    remote = Remote()
    remote.contacts[20] = {"id": 20, "name": "Outro", "custom_attributes": {}}

    async def request(_self, method, path, **kw):
        return await remote.request(method, path, **kw)

    monkeypatch.setattr(Chatwoot, "request", request)
    assert (await client.post("/kanban/import", json={})).status_code == 409
    assert (await client.get("/kanban/import/estimate")).json()["contacts"] == 2
    board = (await client.get("/kanban/board")).json()
    stage = board["stages"][0]
    payload = {
        "mode": "cards",
        "funnel_id": stage["funnel_id"],
        "stage_id": stage["id"],
    }
    assert (await client.post("/kanban/import", json=payload)).status_code == 200
    async with connection() as conn:
        assert await import_one(conn, remote)
        assert (
            await conn.fetchval(
                "SELECT imported_count FROM kb_accounts WHERE account_id=1"
            )
            == 1
        )
        assert (
            await conn.fetchval("SELECT count(*) FROM kb_cards WHERE account_id=1") == 1
        )
        remote.fail_contact = 20
        with pytest.raises(httpx.ConnectError):
            await import_one(conn, remote)
        assert await conn.fetchval(
            "SELECT import_pending FROM kb_accounts WHERE account_id=1"
        ) == [20]
        remote.fail_contact = None
        assert await import_one(conn, remote)
        assert not await import_one(conn, remote)
        assert (
            await conn.fetchval(
                "SELECT imported_count FROM kb_accounts WHERE account_id=1"
            )
            == 2
        )
        assert (
            await conn.fetchval("SELECT count(*) FROM kb_cards WHERE account_id=1") == 2
        )
        assert (
            await conn.fetchval(
                "SELECT activation_status FROM kb_accounts WHERE account_id=1"
            )
            == "ready"
        )
    assert (await client.post("/kanban/import", json=payload)).status_code == 200
    await tick()
    async with connection() as conn:
        assert (
            await conn.fetchval("SELECT count(*) FROM kb_cards WHERE account_id=1") == 2
        )


async def test_reconciliation_repairs_lost_webhook_without_remote_authority(
    client, monkeypatch
):
    remote = Remote()

    async def request(_self, method, path, **kw):
        return await remote.request(method, path, **kw)

    monkeypatch.setattr(Chatwoot, "request", request)
    await client.put(
        "/kanban/contacts/10/task",
        json={"descricao": "Local", "vencimento": "2099-01-01"},
    )
    async with connection() as conn:
        expected = await projection(conn, 1, 10)
        remote.contacts[10]["custom_attributes"] = {
            "kanban_etapa": "EXTERNO",
            "kanban_tarefa": None,
            "outro": "preservar",
        }
        await conn.execute(
            "UPDATE kb_accounts SET reconcile_next_attempt=now() WHERE account_id=1"
        )
    await tick()
    assert all(
        remote.contacts[10]["custom_attributes"][k] == v for k, v in expected.items()
    )
    assert remote.contacts[10]["custom_attributes"]["outro"] == "preservar"
    async with connection() as conn:
        before = await conn.fetchval(
            "SELECT count(*) FROM kb_history WHERE action='espelho_divergente'"
        )
        await conn.execute(
            "UPDATE kb_accounts SET reconcile_next_attempt=now() WHERE account_id=1"
        )
    await tick()
    async with connection() as conn:
        assert (
            await conn.fetchval(
                "SELECT count(*) FROM kb_history WHERE action='espelho_divergente'"
            )
            == before
        )
        assert (
            await conn.fetchval("SELECT message FROM kb_tasks WHERE account_id=1")
            == "Local"
        )


async def test_reconcile_404_preserves_local_state_and_advances(db):
    remote = Remote()
    remote.contacts.clear()
    async with connection() as conn:
        assert await reconcile_one(conn, remote)
        assert (
            await conn.fetchval(
                "SELECT reconcile_cursor FROM kb_accounts WHERE account_id=1"
            )
            == 10
        )
        assert (
            await conn.fetchval("SELECT count(*) FROM kb_cards WHERE account_id=1") == 1
        )


@pytest.mark.parametrize(
    "status,header,delay",
    [
        (401, None, 300),
        (403, None, 300),
        (404, None, 300),
        (429, "80", 80),
        (429, "99999", 3600),
        (429, "bad", 30),
    ],
)
def test_remote_failure_sanitized_and_bounded(status, header, delay):
    exc = httpx.HTTPStatusError(
        "token-secret",
        request=httpx.Request("GET", "http://example.test"),
        response=httpx.Response(
            status, headers={"Retry-After": header} if header else {}
        ),
    )
    diagnostic, actual_delay = failure(exc)
    assert "token-secret" not in diagnostic
    assert actual_delay == delay


async def test_health_distinguishes_empty_queue_from_dead_worker(client):
    async with connection() as conn:
        await conn.execute("TRUNCATE kb_worker_heartbeat")
    result = await client.get("/health")
    assert result.status_code == 503
    assert result.json()["database"] == "ok"
    assert result.json()["worker"] == "stopped"
    await tick()
    assert (await client.get("/health")).status_code == 200
    async with connection() as conn:
        await conn.execute(
            "UPDATE kb_worker_heartbeat SET seen_at=now()-interval '1 hour'"
        )
    assert (await client.get("/health/worker")).status_code == 503


async def test_configuration_and_manifest_admin_only_and_account_scoped(client):
    result = await client.put(
        "/kanban/provisioning",
        json={"mappings": {"origem": "fonte"}, "processing_limit": 2},
    )
    assert result.status_code == 200
    async with connection() as conn:
        assert (
            await conn.fetchval(
                "SELECT attribute_mappings->>'origem' FROM kb_accounts WHERE "
                "account_id=1"
            )
            == "fonte"
        )
        assert (
            await conn.fetchval(
                "SELECT attribute_mappings->>'origem' FROM kb_accounts WHERE "
                "account_id=2"
            )
            == "origem"
        )
    assert (await client.get("/kanban/board")).status_code == 403
    from app.main import app
    from app.security import identity

    async def agent():
        return {"account": 1, "id": 3, "name": "Agente", "role": "agent", "inboxes": []}

    app.dependency_overrides[identity] = agent
    for path in ("/provisioning", "/provisioning/plan", "/import/estimate"):
        assert (await client.get("/kanban" + path)).status_code == 403


async def test_processing_budget_fair_to_other_account(db, monkeypatch):
    remotes = {a: Remote(a) for a in (1, 2)}

    async def request(self, method, path, **kw):
        return await remotes[self.account].request(method, path, **kw)

    monkeypatch.setattr(Chatwoot, "request", request)
    async with connection() as conn:
        await conn.execute("UPDATE kb_accounts SET processing_limit=1")
        for a in (1, 2):
            for contact in (10, 20):
                remotes[a].contacts[contact] = {
                    "id": contact,
                    "name": "Teste",
                    "custom_attributes": {},
                }
                await conn.execute(
                    "INSERT INTO kb_contacts(account_id,contact_id,name) "
                    "VALUES($1,$2,'Teste') ON CONFLICT DO NOTHING",
                    a,
                    contact,
                )
                await conn.execute(
                    "INSERT INTO kb_sync(account_id,contact_id) VALUES($1,$2)",
                    a,
                    contact,
                )
    await tick()
    async with connection() as conn:
        for a in (1, 2):
            assert (
                await conn.fetchval(
                    "SELECT count(*) FROM kb_sync WHERE account_id=$1 AND "
                    "status='synced'",
                    a,
                )
                == 1
            )


@pytest.mark.parametrize("status", [401, 429])
async def test_remote_backoff_stops_account_but_not_other_accounts(
    db, monkeypatch, status
):
    requests = []

    async def request(self, method, path, **kwargs):
        requests.append(self.account)
        if self.account == 1:
            raise httpx.HTTPStatusError(
                "secret",
                request=httpx.Request(method, "http://test"),
                response=httpx.Response(status, headers={"Retry-After": "120"}),
            )
        return {}

    monkeypatch.setattr(Chatwoot, "request", request)
    async with connection() as conn:
        for a in (1, 2):
            for contact in (10, 20):
                await conn.execute(
                    "INSERT INTO kb_contacts(account_id,contact_id,name) "
                    "VALUES($1,$2,'Teste') ON CONFLICT DO NOTHING",
                    a,
                    contact,
                )
                await conn.execute(
                    "INSERT INTO kb_sync(account_id,contact_id) VALUES($1,$2)",
                    a,
                    contact,
                )
    await tick()
    await tick()
    assert requests.count(1) == 1
    assert requests.count(2) == 2
    async with connection() as conn:
        assert await conn.fetchval(
            "SELECT remote_next_attempt>now() FROM kb_accounts WHERE account_id=1"
        )
        assert (
            await conn.fetchval(
                "SELECT count(*) FROM kb_sync WHERE account_id=2 AND status='synced'"
            )
            == 2
        )
        assert "secret" not in str(await conn.fetch("SELECT last_error FROM kb_sync"))


async def test_manifest_preexisting_and_replaced_resource_ownership(db):
    remote = Remote()
    remote.definitions = [
        {
            "id": 100,
            "attribute_key": "kanban_etapa",
            "attribute_model": 1,
            "attribute_display_type": "text",
        }
    ]
    async with connection() as conn:
        await provision_attributes(conn, remote)
        assert (
            await conn.fetchval(
                "SELECT ownership FROM kb_resources WHERE account_id=1 AND "
                "resource_key='contact:kanban_etapa'"
            )
            == "preexisting"
        )
        remote.definitions[1]["id"] = 999
        await provision_attributes(conn, remote)
        assert (
            await conn.fetchval(
                "SELECT ownership FROM kb_resources WHERE account_id=1 AND "
                "resource_key='contact:kanban_tarefa'"
            )
            == "preexisting"
        )


async def test_deleted_contact_during_import_does_not_block_remaining_page(db):
    remote = Remote()
    async with connection() as conn:
        await conn.execute(
            "UPDATE kb_accounts SET import_pending='[99,10]',import_page=2 WHERE "
            "account_id=1"
        )
        assert await import_one(conn, remote)
        assert await import_one(conn, remote)
        assert not await import_one(conn, remote)
        assert (
            await conn.fetchval(
                "SELECT imported_count FROM kb_accounts WHERE account_id=1"
            )
            == 1
        )
        assert (
            await conn.fetchval(
                "SELECT count(*) FROM kb_history WHERE contact_id=99 AND "
                "action='contato_remoto_ausente'"
            )
            == 1
        )


async def test_task_without_card_reconciles_and_closure_is_local(client):
    remote = Remote()
    async with connection() as conn:
        await conn.execute("DELETE FROM kb_card_events WHERE account_id=1")
        await conn.execute("DELETE FROM kb_cards WHERE account_id=1")
    await client.put(
        "/kanban/contacts/10/task",
        json={"descricao": "Local", "vencimento": "2099-01-01"},
    )
    async with connection() as conn:
        async with conn.transaction():
            await lock_contact(conn, 1, 10)
            await refresh_contact(conn, remote, 10)
        assert (
            await conn.fetchval(
                "SELECT count(*) FROM kb_history WHERE action='espelho_divergente'"
            )
            == 1
        )
        assert (await projection(conn, 1, 10))["kanban_tarefa"] == "Local"


async def test_optional_list_conflict_does_not_modify_definition(db):
    remote = Remote()
    remote.definitions = [
        {
            "id": 100,
            "attribute_key": "temperatura",
            "attribute_model": "contact_attribute",
            "attribute_display_type": "list",
            "attribute_values": ["Alta"],
        }
    ]
    async with connection() as conn:
        await provision_attributes(conn, remote)
        assert (
            await conn.fetchval(
                "SELECT attribute_mappings->>'temperatura' FROM kb_accounts WHERE "
                "account_id=1"
            )
            is None
        )
        assert remote.definitions[0]["attribute_values"] == ["Alta"]


async def test_import_receipt_survives_crash_before_progress_summary(db):
    remote = Remote()
    async with connection() as conn:

        class Interrupted:
            def __getattr__(self, name):
                return getattr(conn, name)

            async def execute(self, query, *args):
                if "imported_count=(SELECT" in query:
                    raise RuntimeError("Interrupção simulada após commit")
                return await conn.execute(query, *args)

        with pytest.raises(RuntimeError):
            await import_one(Interrupted(), remote)
        assert (
            await conn.fetchval(
                "SELECT count(*) FROM kb_import_seen WHERE account_id=1"
            )
            == 1
        )
        assert (
            await conn.fetchval(
                "SELECT imported_count FROM kb_accounts WHERE account_id=1"
            )
            == 0
        )
        requests = len(remote.calls)
        await import_one(conn, remote)
        assert len(remote.calls) == requests
        assert (
            await conn.fetchval(
                "SELECT imported_count FROM kb_accounts WHERE account_id=1"
            )
            == 1
        )
        assert (
            await conn.fetchval(
                "SELECT count(*) FROM kb_history WHERE action='metadados_importados'"
            )
            == 1
        )


async def test_import_progress_does_not_deadlock_request_waiting_for_contact(db):
    import asyncio

    entered, release = asyncio.Event(), asyncio.Event()
    remote = Remote()
    original = remote.request

    async def delayed(method, path, **kwargs):
        if path == "/contacts/10":
            entered.set()
            await release.wait()
        return await original(method, path, **kwargs)

    remote.request = delayed

    async def run_import():
        async with connection() as conn:
            await import_one(conn, remote)

    task = asyncio.create_task(run_import())
    await asyncio.wait_for(entered.wait(), 3)
    try:
        async with connection({"account": 1, "id": 3, "role": "administrator"}) as conn:
            waiter = asyncio.create_task(lock_contact(conn, 1, 10))
            release.set()
            await asyncio.wait_for(waiter, 3)
        await asyncio.wait_for(task, 3)
    finally:
        release.set()
        if not task.done():
            task.cancel()
        await asyncio.gather(task, return_exceptions=True)
