"""Paginação, totais e responsabilidade na transação real."""

import httpx

from app.database import connection


async def test_pages_totals_filters_and_detail(client):
    async with connection() as conn:
        await conn.execute("""
            INSERT INTO kb_contacts(account_id,contact_id,name,labels,assignee_id)
            SELECT 1,n,'Contato '||n,'["Cliente"]'::jsonb,7
            FROM generate_series(100,219) n;
            INSERT INTO kb_cards(account_id,contact_id,funnel_id,stage_id,value_cents)
            SELECT 1,n,f.id,s.id,100 FROM generate_series(100,219) n
            CROSS JOIN kb_funnels f JOIN kb_stages s ON s.funnel_id=f.id
            WHERE f.account_id=1 AND s.kind='open';
        """)
    first = (await client.get("/kanban/board?search=Contato&limit=50")).json()
    second = (
        await client.get("/kanban/board?search=Contato&limit=50&offset=50")
    ).json()
    last = (await client.get("/kanban/board?search=Contato&limit=50&offset=100")).json()
    assert [len(p["cards"]) for p in (first, second, last)] == [50, 50, 20]
    assert first["totals"] == second["totals"] == last["totals"]
    assert first["totals"][0]["count"] == 120
    assert first["totals"][0]["value_cents"] == 12000
    assert len({c["id"] for p in (first, second, last) for c in p["cards"]}) == 120
    assert first["contacts"] == []
    card = last["cards"][-1]
    detail = (await client.get(f"/kanban/cards/{card['id']}")).json()
    assert detail["name"] == card["name"]
    for query, expected in [
        ("assignee_id=7", 120),
        ("label=Cliente", 120),
        ("task=none", 121),
        ("search=%25", 0),
        ("search=ContaTo+219", 1),
        ("funnel_id=99999", 0),
        ("contact_id=219", 1),
    ]:
        page = (await client.get("/kanban/board?" + query)).json()
        assert sum(t["count"] for t in page["totals"]) == expected
    assert (await client.get("/kanban/board?limit=101")).status_code == 422


async def test_task_owner_independent_and_transactional(client, monkeypatch):
    body = {"descricao": "Retornar", "vencimento": "2026-10-01"}
    assert (await client.put("/kanban/contacts/10/task", json=body)).status_code == 200
    async with connection() as conn:
        assert (
            await conn.fetchval("SELECT assigned_to FROM kb_tasks WHERE account_id=1")
            == 3
        )

    class Remote:
        async def __aenter__(self):
            return self

        async def __aexit__(self, *_):
            pass

        async def request(self, *_):
            return [{"id": 7, "name": "Ana", "role": "agent"}]

    async def remote(*_):
        return Remote()

    monkeypatch.setattr("app.routers.workspace.Chatwoot.for_account", remote)
    body.update(version=1, assigned_to=7)
    assert (await client.put("/kanban/contacts/10/task", json=body)).status_code == 200
    assert (await client.put("/kanban/contacts/10/task", json=body)).status_code == 409
    body.update(version=2, assigned_to=999)
    assert (await client.put("/kanban/contacts/10/task", json=body)).status_code == 422
    async with connection() as conn:
        await conn.execute("UPDATE kb_contacts SET assignee_id=99 WHERE account_id=1")
        row = await conn.fetchrow("SELECT * FROM kb_tasks WHERE account_id=1")
        assert (
            row["created_by"] == 3 and row["assigned_to"] == 7 and row["version"] == 2
        )
        assert (
            await conn.fetchval("SELECT count(*) FROM kb_history WHERE account_id=1")
            == 2
        )
        assert (
            await conn.fetchval("SELECT version FROM kb_sync WHERE account_id=1") == 2
        )
        after = await conn.fetchval(
            "SELECT after_state FROM kb_history WHERE account_id=1 "
            "AND action='tarefa_criada'"
        )
        assert after["assigned_to"] == 3
    card = (await client.get("/kanban/board")).json()["cards"][0]
    assert card["task_assigned_to"] == 7 and card["task_assignee_name"] == "Ana"
    assert card["assignee_id"] == 99

    async def fail(*_):
        raise httpx.ConnectError("indisponível")

    monkeypatch.setattr("app.routers.workspace.Chatwoot.for_account", fail)
    assert (await client.put("/kanban/contacts/10/task", json=body)).status_code == 503
    body.update(assigned_to=None)
    assert (await client.put("/kanban/contacts/10/task", json=body)).status_code == 200
