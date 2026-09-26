"""Valor atual nas métricas, data real de movimentos, importação e reparo."""

from datetime import UTC, date, datetime, timedelta

import pytest

from app import maintenance
from app.chatwoot_client import Chatwoot
from app.database import connection
from app.recovery import import_one
from tests.test_phase2 import Remote as PhaseRemote

OPENED = datetime(2026, 9, 22, 14, tzinfo=UTC)


async def stages(client):
    board = (await client.get("/kanban/board")).json()
    by_kind = {s["kind"]: s for s in board["stages"]}
    return board["cards"][0], by_kind


async def summary(client):
    today = datetime.now(UTC).date()
    result = await client.get(
        f"/kanban/metrics/summary?start={today - timedelta(days=30)}"
        f"&end={today}&period=day"
    )
    assert result.status_code == 200, result.text
    return result.json()["current"]


async def test_value_filled_after_win_counts_as_revenue(client):
    card, kind = await stages(client)
    moved = await client.patch(
        f"/kanban/cards/{card['id']}",
        json={"version": card["version"], "stage_id": kind["won"]["id"]},
    )
    assert moved.status_code == 200
    async with connection() as conn:
        before = await conn.fetchrow(
            "SELECT version,position,stage_entered_at FROM kb_cards WHERE id=$1",
            card["id"],
        )
    valued = await client.patch(
        f"/kanban/cards/{card['id']}/value",
        json={"version": before["version"], "value_cents": 500000},
    )
    assert valued.status_code == 200
    async with connection() as conn:
        after = await conn.fetchrow(
            "SELECT position,stage_entered_at,value_cents FROM kb_cards WHERE id=$1",
            card["id"],
        )
        action = await conn.fetchval(
            "SELECT action FROM kb_history ORDER BY id DESC LIMIT 1"
        )
    assert (after["position"], after["stage_entered_at"]) == (
        before["position"],
        before["stage_entered_at"],
    )
    assert after["value_cents"] == 500000 and action == "valor_atualizado"
    result = await summary(client)
    assert result["wins"] == 1 and result["revenue"] == 500000
    assert result["average_ticket"] == 500000
    stale = await client.patch(
        f"/kanban/cards/{card['id']}/value",
        json={"version": before["version"], "value_cents": 1},
    )
    assert stale.status_code == 409


async def test_move_with_real_date(client):
    card, kind = await stages(client)
    async with connection() as conn:
        await conn.execute(
            "UPDATE kb_cards SET created_at=$1,stage_entered_at=$1 WHERE id=$2",
            OPENED,
            card["id"],
        )
    base = {"version": card["version"], "stage_id": kind["won"]["id"]}
    for when, error in [
        ((datetime.now(UTC) + timedelta(days=1)).isoformat(), "futuro"),
        ("2026-09-01T10:00:00", "anterior"),
    ]:
        response = await client.patch(
            f"/kanban/cards/{card['id']}", json={**base, "occurred_at": when}
        )
        assert response.status_code == 422 and error in response.json()["detail"]
    same = await client.patch(
        f"/kanban/cards/{card['id']}",
        json={**base, "stage_id": card["stage_id"], "occurred_at": "2026-09-23"},
    )
    assert same.status_code == 422
    moved = await client.patch(
        f"/kanban/cards/{card['id']}",
        json={**base, "occurred_at": "2026-09-23T12:00:00"},
    )
    assert moved.status_code == 200, moved.text
    async with connection() as conn:
        row = await conn.fetchrow(
            "SELECT won_at,stage_entered_at FROM kb_cards WHERE id=$1", card["id"]
        )
        event = await conn.fetchval(
            "SELECT created_at FROM kb_card_events WHERE card_id=$1 "
            "AND event_type='moved'",
            card["id"],
        )
        leftover = await conn.fetchval(
            "SELECT current_setting('kanban.occurred_at',true)"
        )
    expected = datetime(2026, 9, 23, 15, tzinfo=UTC)
    assert row["won_at"] == row["stage_entered_at"] == event == expected
    assert not leftover


async def test_agent_cannot_backdate(client):
    from app.main import app
    from app.security import identity

    card, kind = await stages(client)

    async def agent():
        return {"account": 1, "id": 4, "name": "Agente", "role": "agent", "inboxes": []}

    app.dependency_overrides[identity] = agent
    response = await client.patch(
        f"/kanban/cards/{card['id']}",
        json={
            "version": card["version"],
            "stage_id": kind["won"]["id"],
            "occurred_at": "2026-09-23",
        },
    )
    assert response.status_code in (403, 404)


async def test_stage_positions_stay_unique(client):
    _, kind = await stages(client)
    funnel = kind["open"]["funnel_id"]
    taken = await client.post(
        f"/kanban/funnels/{funnel}/stages",
        json={"name": "Duplicada", "position": kind["won"]["position"]},
    )
    assert taken.status_code == 409
    swapped = await client.put(
        f"/kanban/stages/{kind['open']['id']}",
        json={"name": "Novo", "kind": "open", "position": kind["won"]["position"]},
    )
    assert swapped.status_code == 200
    async with connection() as conn:
        positions = dict(
            await conn.fetch(
                "SELECT id,position FROM kb_stages WHERE funnel_id=$1", funnel
            )
        )
    assert positions[kind["open"]["id"]] == kind["won"]["position"]
    assert positions[kind["won"]["id"]] == kind["open"]["position"]


class Remote(PhaseRemote):
    """Contato 20 abriu a primeira conversa dias antes da importação."""

    async def request(self, method, path, **kwargs):
        if path == "/contacts/20/conversations":
            return {
                "payload": [
                    {"id": 7, "created_at": OPENED.timestamp() + 86400},
                    {"id": 6, "created_at": OPENED.timestamp()},
                ]
            }
        return await super().request(method, path, **kwargs)


async def test_import_uses_first_contact_date(client, monkeypatch):
    remote = Remote()
    remote.contacts = {20: {"id": 20, "name": "Lead", "custom_attributes": {}}}

    async def request(_self, method, path, **kw):
        return await remote.request(method, path, **kw)

    monkeypatch.setattr(Chatwoot, "request", request)
    _, kind = await stages(client)
    payload = {
        "mode": "cards",
        "funnel_id": kind["open"]["funnel_id"],
        "stage_id": kind["open"]["id"],
    }
    assert (await client.get("/kanban/import/estimate")).status_code == 200
    started = await client.post("/kanban/import", json=payload)
    assert started.status_code == 200, started.text
    async with connection() as conn:
        assert await import_one(conn, remote)
        card = await conn.fetchrow(
            "SELECT id,created_at,stage_entered_at FROM kb_cards WHERE contact_id=20"
        )
        event = await conn.fetchval(
            "SELECT created_at FROM kb_card_events WHERE card_id=$1 "
            "AND event_type='created'",
            card["id"],
        )
    assert card["created_at"] == card["stage_entered_at"] == event == OPENED


async def test_repair_backfills_creation_and_win_date(client, monkeypatch, capsys):
    remote = Remote()

    async def request(_self, method, path, **kw):
        return await remote.request(method, path, **kw)

    monkeypatch.setattr(Chatwoot, "request", request)

    async def keep_pool():
        return None

    # O comando abre e fecha o pool; nos testes o pool é da fixture.
    monkeypatch.setattr(maintenance, "init_pool", keep_pool)
    monkeypatch.setattr(maintenance, "close_pool", keep_pool)
    today = datetime.now(UTC)
    async with connection() as conn:
        await conn.execute(
            "INSERT INTO kb_contacts(account_id,contact_id,name) VALUES(1,20,'Lead')"
        )
        card = await conn.fetchval(
            """INSERT INTO kb_cards(account_id,contact_id,funnel_id,stage_id)
            SELECT 1,20,funnel_id,id FROM kb_stages WHERE account_id=1
            AND kind='open' RETURNING id"""
        )
    _, kind = await stages(client)
    version = 1
    await client.patch(
        f"/kanban/cards/{card}",
        json={"version": version, "stage_id": kind["won"]["id"]},
    )
    day = (today.astimezone(maintenance.BRAZIL)).date()
    args = maintenance.parser().parse_args(
        [
            "--account",
            "1",
            "--dry-run",
            "--backfill-created",
            day.isoformat(),
            "--won-at",
            f"{card}=2026-09-23",
        ]
    )
    await maintenance.main(args)
    assert "Simulação: 1 cartões" in capsys.readouterr().out
    async with connection() as conn:
        assert (
            await conn.fetchval("SELECT created_at FROM kb_cards WHERE id=$1", card)
            > OPENED
        )
    args.dry_run = False
    await maintenance.main(args)
    await maintenance.main(args)
    async with connection() as conn:
        row = await conn.fetchrow(
            "SELECT created_at,won_at,stage_entered_at FROM kb_cards WHERE id=$1",
            card,
        )
        created = await conn.fetchval(
            "SELECT created_at FROM kb_card_events WHERE card_id=$1 "
            "AND event_type='created'",
            card,
        )
        won = await conn.fetchval(
            "SELECT created_at FROM kb_card_events WHERE card_id=$1 "
            "AND event_type='moved'",
            card,
        )
        logged = await conn.fetchval(
            "SELECT count(*) FROM kb_history WHERE action='manutencao_metricas'"
        )
    noon = maintenance.noon(date(2026, 9, 23))
    assert row["created_at"] == created == OPENED
    assert row["won_at"] == row["stage_entered_at"] == won == noon
    assert logged == 2
    async with connection() as conn:
        with pytest.raises(SystemExit):
            await maintenance.set_won_at(conn, 1, card, date(2026, 9, 1))
