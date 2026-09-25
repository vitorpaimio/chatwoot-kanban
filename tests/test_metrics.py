from datetime import datetime
from zoneinfo import ZoneInfo

import pytest

from app.database import connection
from app.metrics.service import cached
from app.routers.metrics import comparison

TZ = ZoneInfo("America/Sao_Paulo")


def dt(day):
    return datetime(2026, 8, day, 12, tzinfo=TZ)


@pytest.fixture
async def metric_data(client):
    async with connection() as c:
        await c.execute("DELETE FROM kb_card_events WHERE account_id=1")
        await c.execute("DELETE FROM kb_cards WHERE account_id=1")
        await c.execute(
            "INSERT INTO kb_agents VALUES(1,3,'Ana','administrator') ON C"
            "ONFLICT DO NOTHING"
        )
        f = await c.fetchval("SELECT id FROM kb_funnels WHERE account_id=1")
        stages = await c.fetch(
            "SELECT id,kind FROM kb_stages WHERE account_id=1 ORDER BY position"
        )
        novo, won, lost = [s["id"] for s in stages]
        proposal = await c.fetchval(
            (
                "INSERT INTO kb_stages(account_id,funnel_id,name,position) VA"
                "LUES(1,$1,'Proposta',1536) RETURNING id"
            ),
            f,
        )
        ids = []

        async def event(card, stage, when, value, typ, previous=None, reason=None):
            await c.execute(
                """INSERT INTO kb_card_events(account_id,card_id,event_type,stage_id,
 previous_stage_id,stage_kind,stage_position,value_cents,lost_reason,assignee_id,
 inbox_id,source,campaign,entered_at,created_at)
            SELECT 1,$1,$2,id,$3,kind,position,$4,$5,3,1,'Site','Agosto',$6,$6 FROM
 kb_stages WHERE id=$7""",
                card,
                typ,
                previous,
                value,
                reason,
                dt(when),
                stage,
            )

        for i, day, value in [
            (21, 1, 10000),
            (22, 10, 20000),
            (23, 12, 30000),
            (24, 2, 40000),
            (25, 1, 0),
        ]:
            await c.execute(
                (
                    "INSERT INTO kb_contacts(account_id,contact_id,name,assignee_"
                    "id,inbox_id) VALUES(1,$1,$2,3,1)"
                ),
                i,
                f"Contato {i}",
            )
            card = await c.fetchval(
                (
                    "INSERT INTO kb_cards(account_id,contact_id,funnel_id,stage_i"
                    "d,value_cents,created_at) VALUES(1,$1,$2,$3,$4,$5) RETURNING"
                    " id"
                ),
                i,
                f,
                novo,
                value,
                dt(day),
            )
            await c.execute(
                "DELETE FROM kb_card_events WHERE account_id=1 AND card_id=$1", card
            )
            await event(card, novo, day, value, "created")
            ids.append(card)
        await event(ids[0], proposal, 11, 10000, "moved", novo)
        await event(ids[0], won, 13, 10000, "moved", proposal)
        await event(ids[1], lost, 12, 20000, "moved", novo, "Preço")
        for contact, due, closed in [(23, 14, None), (24, 15, 15), (21, 12, 13)]:
            await c.execute(
                (
                    "INSERT INTO kb_tasks(account_id,contact_id,message,due_date,"
                    "status,created_at,closed_at) VALUES(1,$1,'Tarefa',$2,$3,$4,$"
                    "5)"
                ),
                contact,
                dt(due).date(),
                "closed" if closed else "active",
                dt(10),
                dt(closed) if closed else None,
            )
    return {
        "funnel": f,
        "ids": ids,
        "novo": novo,
        "proposal": proposal,
        "won": won,
        "lost": lost,
    }


async def block(client, name, query=""):
    response = await client.get(
        f"/kanban/metrics/{name}?start=2026-08-10&end=2026-08-16{query}"
    )
    assert response.status_code == 200, response.text
    return response.json()


async def test_summary_exact_definitions(client, metric_data):
    r = await block(client, "summary")
    assert r["current"] == {
        "leads": 2,
        "ongoing": 3,
        "wins": 1,
        "revenue": 10000,
        "losses": 1,
        "win_rate": 50,
        "average_ticket": 10000,
        "open_value": 70000,
        "cycle_days": 12,
    }
    assert r["previous"]["wins"] == 0
    assert r["variation"]["leads"] is None
    assert r["period"]["previous_start"] == "2026-08-03"
    assert r["period"]["previous_end"] == "2026-08-09"


async def test_funnel_conversion_dwell_and_stale(client, metric_data):
    r = (await block(client, "funnel"))["current"]
    novo = next(s for s in r["rows"] if s["id"] == metric_data["novo"])
    proposal = next(s for s in r["rows"] if s["id"] == metric_data["proposal"])
    assert novo["quantity"] == 2 and novo["conversion"] == 50
    assert novo["dwell_days"] == 6
    assert proposal["conversion"] == 100 and proposal["next_conversion"] == 100
    assert proposal["dwell_days"] == 2
    assert {"color", "kind"} <= novo.keys() and novo["kind"] == "open"
    assert [c["id"] for c in r["stale"]] == [metric_data["ids"][4]]


async def test_losses_sources_team_tasks_timeline(client, metric_data):
    loss = (await block(client, "losses"))["current"]["rows"][0]
    assert (
        loss["reason"] == "Preço"
        and loss["from_stage"] == "Novo"
        and loss["quantity"] == 1
    )
    source = (await block(client, "sources"))["current"]["rows"][0]
    assert (
        source["source"],
        source["campaign"],
        source["leads"],
        source["wins"],
        source["win_rate"],
        source["revenue"],
    ) == ("Site", "Agosto", 2, 1, 50, 10000)
    team = (await block(client, "team"))["current"]["rows"][0]
    assert team["leads"] == 2 and team["wins"] == 1 and team["overdue_tasks"] == 1
    tasks = (await block(client, "tasks"))["current"]
    assert tasks == {"open": 1, "overdue": 1, "completed": 2, "on_time_rate": 50}
    days = (await block(client, "timeline"))["current"]["rows"]
    assert (
        len(days) == 7
        and sum(d["leads"] for d in days) == 2
        and sum(d["wins"] for d in days) == 1
    )


async def test_empty_period_zero_division_and_csv(client, metric_data):
    empty = await client.get("/kanban/metrics/summary?start=2020-01-01&end=2020-01-01")
    assert empty.json()["current"]["win_rate"] == 0
    assert empty.json()["current"]["average_ticket"] is None
    assert empty.json()["current"]["cycle_days"] is None
    # Sem tarefa concluída não há taxa de prazo: nulo, e não 0% (UX-43).
    tasks = await client.get("/kanban/metrics/tasks?start=2020-01-01&end=2020-01-01")
    assert tasks.json()["current"]["completed"] == 0
    assert tasks.json()["current"]["on_time_rate"] is None
    assert tasks.json()["variation"]["on_time_rate"] is None
    assert (await block(client, "summary", "&assignee_id=999"))["current"]["leads"] == 0
    for name in ("summary", "funnel", "losses", "sources", "tasks", "timeline"):
        r = await client.get(
            f"/kanban/metrics/{name}?start=2020-01-01&end=2020-01-01&format=csv"
        )
        assert r.status_code == 200 and "text/csv" in r.headers["content-type"]
    async with connection() as conn:
        foreign = await conn.fetchval("SELECT id FROM kb_funnels WHERE account_id=2")
    assert (
        await client.get(f"/kanban/metrics/summary?funnel_id={foreign}")
    ).status_code == 404
    assert (
        comparison(0, 0) == 0
        and comparison(10, 0) is None
        and comparison(20, 10) == 100
    )


async def test_loss_required_and_event_snapshot(client):
    board = (await client.get("/kanban/board")).json()
    card = board["cards"][0]
    stage = next(s for s in board["stages"] if s["kind"] == "lost")
    body = {"version": card["version"], "stage_id": stage["id"]}
    assert (
        await client.patch(f"/kanban/cards/{card['id']}", json=body)
    ).status_code == 422
    body["lost_reason"] = "Outro: Prazo incompatível"
    assert (
        await client.patch(f"/kanban/cards/{card['id']}", json=body)
    ).status_code == 200
    async with connection() as conn:
        e = await conn.fetchrow(
            (
                "SELECT * FROM kb_card_events WHERE account_id=1 AND card_id="
                "$1 ORDER BY id DESC LIMIT 1"
            ),
            card["id"],
        )
        assert (
            e["lost_reason"] == body["lost_reason"]
            and e["previous_stage_id"] == card["stage_id"]
        )
        assert await conn.fetchval(
            "SELECT lost_at IS NOT NULL FROM kb_cards WHERE id=$1", card["id"]
        )


async def test_cache_is_account_scoped_and_expires(client):
    calls = []

    async def fetch():
        calls.append(1)
        return {"value": len(calls)}

    async with connection() as conn:
        assert (await cached(conn, 1, "test", fetch))["value"] == 1
        assert (await cached(conn, 1, "test", fetch))["value"] == 1
        assert (await cached(conn, 2, "test", fetch))["value"] == 2
        await conn.execute(
            "UPDATE kb_metrics_cache SET fetched_at=now()-interval '6 minutes'"
        )
        assert (await cached(conn, 1, "test", fetch))["value"] == 3


async def test_due_date_includes_whole_last_day(client, metric_data):
    async with connection() as conn:
        await conn.execute(
            "UPDATE kb_tasks SET due_date='2026-08-16' "
            "WHERE account_id=1 AND status='active'"
        )
    tasks = (await block(client, "tasks"))["current"]
    assert tasks["open"] == 1 and tasks["overdue"] == 0
    after = await client.get("/kanban/metrics/tasks?start=2026-08-17&end=2026-08-17")
    assert after.json()["current"]["overdue"] == 1


async def test_contact_dimensions_copy_clear_and_isolate(client):
    async with connection() as conn:
        await conn.execute(
            "UPDATE kb_contacts SET remote_attributes=$1,assignee_id=3,inbox_id=4 "
            "WHERE account_id=1 AND contact_id=10",
            {"origem": "Site", "campanha": "Setembro", "temperatura": "Quente"},
        )
        row = await conn.fetchrow("SELECT * FROM kb_cards WHERE account_id=1")
        assert (
            row["source"],
            row["campaign"],
            row["temperature"],
            row["inbox_id"],
        ) == ("Site", "Setembro", "Quente", 4)
        foreign = await conn.fetchrow("SELECT * FROM kb_cards WHERE account_id=2")
        assert foreign["source"] is None and foreign["inbox_id"] is None
        await conn.execute(
            "UPDATE kb_contacts SET remote_attributes='{}',inbox_id=NULL "
            "WHERE account_id=1"
        )
        event = await conn.fetchrow(
            "SELECT * FROM kb_card_events WHERE account_id=1 ORDER BY id DESC LIMIT 1"
        )
        assert event["source"] is None and event["campaign"] is None
        assert event["temperature"] is None and event["inbox_id"] is None


async def test_service_delegated_to_chatwoot(client):
    for format in ("json", "csv"):
        response = await client.get(f"/kanban/metrics/service?format={format}")
        assert response.status_code == 409
        assert "Chatwoot" in response.json()["detail"]


async def test_options_report_configured_dimensions(client):
    async with connection() as conn:
        await conn.execute(
            "UPDATE kb_accounts SET attribute_mappings=$1 WHERE account_id=1",
            {"origem": "fonte", "campanha": None, "temperatura": None},
        )
    result = (await client.get("/kanban/metrics/options")).json()
    assert result["dimensions"] == {"source": True, "campaign": False}


async def test_source_and_campaign_aggregations(client, metric_data):
    result = (await block(client, "sources"))["current"]
    assert result["origins"][0]["source"] == "Site"
    assert result["origins"][0]["leads"] == 2
    assert result["campaigns"][0]["campaign"] == "Agosto"
    assert result["campaigns"][0]["win_rate"] == 50


async def test_stage_classification_updates_balance_without_fake_win(client):
    async with connection() as conn:
        stage = await conn.fetchval("SELECT stage_id FROM kb_cards WHERE account_id=1")
        await conn.execute(
            "UPDATE kb_stages SET kind='won' WHERE account_id=1 AND id=$1", stage
        )
    result = (await client.get("/kanban/metrics/summary")).json()["current"]
    assert result["ongoing"] == 0
    assert result["wins"] == 0
