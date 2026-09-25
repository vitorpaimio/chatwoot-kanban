"""Carregamento do quadro: funil padrão, cache de arquivos e responsável."""

import re

from app.database import connection, lock_contact
from app.services import refresh_contact


async def test_board_without_funnel_opens_primary(client):
    other = await client.post("/kanban/funnels", json={"name": "Outro"})
    board = (await client.get("/kanban/board")).json()
    async with connection() as conn:
        primary = await conn.fetchval(
            "SELECT id FROM kb_funnels WHERE account_id=1 AND is_primary"
        )
    assert board["funnel_id"] == primary
    assert {c["funnel_id"] for c in board["cards"]} == {primary}
    chosen = await client.get(f"/kanban/board?funnel_id={other.json()['id']}")
    assert chosen.json()["funnel_id"] == other.json()["id"]


async def test_static_assets_are_versioned_and_cached(client):
    page = await client.get("/kanban")
    assert page.headers["cache-control"] == "no-store"
    assets = re.findall(r'"(/kanban/static/[^"]+\?v=[0-9a-f]+)"', page.text)
    assert {a.split("?")[0].rsplit("/", 1)[1] for a in assets} == {
        "kanban.css",
        "theme.js",
        "helpers.js",
        "ui.js",
        "kanban.js",
    }
    versioned = await client.get(assets[0])
    assert versioned.headers["cache-control"] == "public, max-age=31536000, immutable"
    plain = await client.get(assets[0].split("?")[0])
    assert plain.headers["cache-control"] == "no-cache"
    metrics = await client.get("/kanban/metricas")
    assert "/kanban/static/vendor/chart.umd.js?v=" in metrics.text
    api = await client.get("/kanban/board")
    assert api.headers["cache-control"] == "no-store"


class Remote:
    """Contato com uma conversa resolvida recente e outra aberta mais antiga."""

    account = 1

    async def request(self, _method, path, **_kwargs):
        if path.endswith("/conversations"):
            return {
                "payload": [
                    {
                        "id": 1,
                        "status": "open",
                        "inbox_id": 5,
                        "last_activity_at": 100,
                        "meta": {"assignee": {"id": 7, "name": "Ana"}},
                    },
                    {
                        "id": 2,
                        "status": "resolved",
                        "inbox_id": 5,
                        "last_activity_at": 200,
                        "meta": {"assignee": {"id": 8, "name": "Bruno"}},
                    },
                ]
            }
        if path.endswith("/labels"):
            return {"payload": []}
        return {"payload": {"id": 10, "name": "Maria"}}


async def test_open_conversation_defines_assignee(db):
    async with connection() as conn, conn.transaction():
        await lock_contact(conn, 1, 10)
        await refresh_contact(conn, Remote(), 10)
        row = await conn.fetchrow(
            "SELECT assignee_name,conversation_id FROM kb_contacts "
            "WHERE account_id=1 AND contact_id=10"
        )
    assert (row["assignee_name"], row["conversation_id"]) == ("Ana", 1)
