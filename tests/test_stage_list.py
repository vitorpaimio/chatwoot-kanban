"""Atributo Funil / Etapa como lista editável nos dois sentidos."""

from app.database import connection, lock_contact
from app.provisioning.attributes import attribute_plan
from app.services import (
    REMOTE_LOSS_REASON,
    projection,
    refresh_contact,
    sync_stage_options,
)


class Remote:
    """Chatwoot mínimo: um contato, definições e registro das chamadas."""

    account = 1

    def __init__(self, value=None):
        self.attributes = {"kanban_etapa": value}
        self.calls = []

    async def request(self, method, path, **kwargs):
        self.calls.append((method, path, kwargs.get("json")))
        if method == "PATCH":
            return {"id": 100, **kwargs["json"]}
        if path.endswith("/conversations") or path.endswith("/labels"):
            return {"payload": []}
        return {
            "payload": {
                "id": 10,
                "name": "Maria",
                "custom_attributes": {**self.attributes},
            }
        }


async def remember_text_attribute(conn):
    await conn.execute(
        """INSERT INTO kb_resources(account_id,resource_type,resource_key,
        remote_id,ownership,definition) VALUES(1,'attribute',
        'contact:kanban_etapa',100,'created',$1)""",
        {"attribute_key": "kanban_etapa", "attribute_display_type": "text"},
    )


async def webhook_refresh(remote):
    async with connection() as conn, conn.transaction():
        await lock_contact(conn, 1, 10)
        await refresh_contact(conn, remote, 10, apply_remote=True)


async def card_stages(conn):
    return await conn.fetch(
        """SELECT f.name AS funnel,s.name AS stage,c.lost_reason FROM kb_cards c
        JOIN kb_funnels f ON f.id=c.funnel_id JOIN kb_stages s ON s.id=c.stage_id
        WHERE c.account_id=1 ORDER BY c.id"""
    )


def test_plan_accepts_legacy_text_stage_attribute():
    legacy = {
        "id": 1,
        "attribute_key": "kanban_etapa",
        "attribute_model": "contact_attribute",
        "attribute_display_type": "text",
    }
    item = next(i for i in attribute_plan([legacy], {}) if i["key"] == "kanban_etapa")
    assert item["status"] == "reuse"
    assert item["payload"]["attribute_display_type"] == 6
    assert item["payload"]["attribute_values"][0] == "Funil principal / Novo"


async def test_options_follow_active_funnels_and_convert_text(client):
    remote = Remote()
    async with connection() as conn:
        await remember_text_attribute(conn)
        await sync_stage_options(conn, remote)
        await sync_stage_options(conn, remote)
    assert remote.calls == [
        (
            "PATCH",
            "/custom_attribute_definitions/100",
            {
                "attribute_display_type": 6,
                "attribute_values": [
                    "Principal / Novo",
                    "Principal / Ganho",
                    "Principal / Perdido",
                ],
            },
        )
    ]
    await client.post("/kanban/funnels", json={"name": "Renovação"})
    async with connection() as conn:
        await sync_stage_options(conn, remote)
    assert remote.calls[-1][2]["attribute_values"][-1] == "Renovação / Novo"


async def test_list_choice_moves_card_and_is_not_reapplied(db):
    remote = Remote("Principal / Ganho")
    await webhook_refresh(remote)
    async with connection() as conn:
        rows = await card_stages(conn)
        assert [(r["funnel"], r["stage"]) for r in rows] == [("Principal", "Ganho")]
        assert (await projection(conn, 1, 10))["kanban_etapa"] == "Principal / Ganho"
        assert (
            await conn.fetchval(
                "SELECT actor_name FROM kb_history WHERE action='cartao_movido'"
            )
            == "Chatwoot"
        )
        assert await conn.fetchval("SELECT status FROM kb_sync") == "pending"
        await conn.execute(
            "UPDATE kb_sync SET status='synced',projection=$1",
            {"kanban_etapa": "Principal / Ganho"},
        )
    await webhook_refresh(remote)
    async with connection() as conn:
        assert (
            await conn.fetchval(
                "SELECT count(*) FROM kb_history WHERE action='cartao_movido'"
            )
            == 1
        )


async def test_lost_choice_records_reason_and_new_funnel_creates_card(client):
    await client.post("/kanban/funnels", json={"name": "Renovação"})
    await webhook_refresh(Remote("Principal / Perdido"))
    async with connection() as conn:
        assert (await card_stages(conn))[0]["lost_reason"] == REMOTE_LOSS_REASON
        await conn.execute("UPDATE kb_sync SET status='synced'")
    await webhook_refresh(Remote("Renovação / Novo"))
    async with connection() as conn:
        rows = await card_stages(conn)
        assert [(r["funnel"], r["stage"]) for r in rows] == [
            ("Principal", "Perdido"),
            ("Renovação", "Novo"),
        ]
        assert (await projection(conn, 1, 10))["kanban_etapa"] == "Renovação / Novo"


async def test_pending_local_move_and_unknown_value_win(client):
    data = (await client.get("/kanban/board")).json()
    card = data["cards"][0]
    await client.patch(
        f"/kanban/cards/{card['id']}",
        json={"version": 1, "stage_id": data["stages"][1]["id"]},
    )
    await webhook_refresh(Remote("Principal / Novo"))
    async with connection() as conn:
        assert (await card_stages(conn))[0]["stage"] == "Ganho"
        await conn.execute("UPDATE kb_sync SET status='synced'")
    await webhook_refresh(Remote("Inexistente / Novo"))
    async with connection() as conn:
        assert (await card_stages(conn))[0]["stage"] == "Ganho"
        assert (
            await conn.fetchval(
                "SELECT count(*) FROM kb_history WHERE action='espelho_divergente'"
            )
            == 2
        )
