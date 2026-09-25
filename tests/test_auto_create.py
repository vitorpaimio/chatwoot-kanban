"""Criação automática de negociações para leads novos."""

import uuid

from app.database import connection
from app.worker import process_delivery


class Remote:
    """Chatwoot mínimo com um contato por identificador e uma conversa."""

    account = 1

    def __init__(self, inbox_id=7):
        self.inbox_id = inbox_id

    async def request(self, _method, path, **_kwargs):
        contact = int(path.split("/")[2])
        if path.endswith("/conversations"):
            return {"payload": [{"id": 500 + contact, "inbox_id": self.inbox_id}]}
        if path.endswith("/labels"):
            return {"payload": []}
        return {"payload": {"id": contact, "name": f"Lead {contact}"}}


async def deliver(contact, inbox_id=7, event="conversation_created"):
    async with connection() as conn:
        row = await conn.fetchrow(
            """INSERT INTO kb_deliveries(account_id,delivery_id,event_type,
            contact_id,payload) VALUES(1,$1,$2,$3,$4) RETURNING *""",
            str(uuid.uuid4()),
            event,
            contact,
            {"event": event, "inbox_id": inbox_id, "account": {"id": 1}},
        )
        await process_delivery(conn, Remote(inbox_id), row)
        status = await conn.fetchval(
            "SELECT status FROM kb_deliveries WHERE id=$1", row["id"]
        )
        assert status == "processed"


async def cards(contact):
    async with connection() as conn:
        return await conn.fetch(
            """SELECT f.name AS funnel,s.name AS stage,c.conversation_id,
            c.conversation_inbox_id FROM kb_cards c
            JOIN kb_funnels f ON f.id=c.funnel_id JOIN kb_stages s ON s.id=c.stage_id
            WHERE c.account_id=1 AND c.contact_id=$1 ORDER BY c.id""",
            contact,
        )


async def funnel(client, name="Leads", **settings):
    created = await client.post("/kanban/funnels", json={"name": name, **settings})
    assert created.status_code == 200, created.text
    return created.json()["id"]


async def test_new_funnel_uses_first_stage_and_saves_inboxes(client):
    fid = await funnel(client, auto_create=True, auto_create_inboxes=[9, 7, 7])
    async with connection() as conn:
        row = await conn.fetchrow(
            """SELECT s.name,f.auto_create_inboxes FROM kb_funnels f JOIN kb_stages s
            ON s.id=f.auto_create_stage_id WHERE f.id=$1""",
            fid,
        )
    assert (row["name"], row["auto_create_inboxes"]) == ("Novo", [7, 9])
    board = (await client.get("/kanban/board")).json()
    saved = next(f for f in board["funnels"] if f["id"] == fid)
    assert saved["auto_create_inboxes"] == [7, 9]


async def test_first_conversation_creates_card_once(client):
    await funnel(client, auto_create=True)
    await deliver(20)
    await deliver(20)
    rows = await cards(20)
    assert [(r["funnel"], r["stage"]) for r in rows] == [("Leads", "Novo")]
    assert (rows[0]["conversation_id"], rows[0]["conversation_inbox_id"]) == (520, 7)
    async with connection() as conn:
        history = await conn.fetchrow(
            "SELECT actor_name,after_state FROM kb_history WHERE action='cartao_criado'"
        )
        assert history["actor_name"] == "Criação automática"
        assert history["after_state"]["automatico"] is True
        assert (
            await conn.fetchval("SELECT status FROM kb_sync WHERE contact_id=20")
            == "pending"
        )


async def test_existing_or_deleted_deal_blocks_new_card(client):
    principal = (await client.get("/kanban/board")).json()["funnels"][0]
    await client.put(
        f"/kanban/funnels/{principal['id']}",
        json={"name": "Principal", "position": 1024, "auto_create": True},
    )
    await deliver(10)
    assert len(await cards(10)) == 1
    await deliver(30)
    async with connection() as conn:
        card = await conn.fetchval("SELECT id FROM kb_cards WHERE contact_id=30")
    deleted = await client.request(
        "DELETE", f"/kanban/cards/{card}", json={"version": 1}
    )
    assert deleted.status_code == 200, deleted.text
    await deliver(30)
    async with connection() as conn:
        assert (
            await conn.fetchval("SELECT count(*) FROM kb_cards WHERE contact_id=30")
            == 1
        )


async def test_inbox_filter_and_other_events(client):
    await funnel(client, auto_create=True, auto_create_inboxes=[8])
    await deliver(40, inbox_id=7)
    await deliver(41, inbox_id=8, event="conversation_updated")
    assert await cards(40) == [] and await cards(41) == []
    await deliver(42, inbox_id=8)
    assert [r["funnel"] for r in await cards(42)] == ["Leads"]


async def test_entry_stage_must_be_open_and_follows_stage_changes(client):
    fid = await funnel(client)
    stages = (await client.get("/kanban/board")).json()["stages"]
    novo = next(s for s in stages if s["funnel_id"] == fid)
    body = {"name": "Leads", "position": 2048, "auto_create": True}
    won = await client.post(
        f"/kanban/funnels/{fid}/stages",
        json={"name": "Fechado", "kind": "won", "position": 4096},
    )
    rejected = await client.put(
        f"/kanban/funnels/{fid}",
        json={**body, "auto_create_stage_id": won.json()["id"]},
    )
    assert rejected.status_code == 422
    other = await client.post(
        f"/kanban/funnels/{fid}/stages", json={"name": "Triagem", "position": 512}
    )
    tid = other.json()["id"]
    assert (
        await client.put(
            f"/kanban/funnels/{fid}", json={**body, "auto_create_stage_id": tid}
        )
    ).status_code == 200
    await deliver(50)
    assert [r["stage"] for r in await cards(50)] == ["Triagem"]
    archived = await client.post(
        f"/kanban/stages/{tid}/archive", json={"destination_id": novo["id"]}
    )
    assert archived.status_code == 200
    async with connection() as conn:
        assert (
            await conn.fetchval(
                "SELECT auto_create_stage_id FROM kb_funnels WHERE id=$1", fid
            )
            is None
        )
    await deliver(51)
    assert await cards(51) == []
