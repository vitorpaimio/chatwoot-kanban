from app.database import connection
from app.main import app
from app.security import identity
from app.services import projection


async def follow_up():
    """Cria o funil de destino com uma etapa aberta e uma de perda."""
    async with connection() as conn:
        fid = await conn.fetchval(
            "INSERT INTO kb_funnels(account_id,name) VALUES(1,'Follow up') "
            "RETURNING id"
        )
        stages = [
            await conn.fetchval(
                "INSERT INTO kb_stages(account_id,funnel_id,name,kind,position) "
                "VALUES(1,$1,$2,$3,$4) RETURNING id",
                fid,
                name,
                kind,
                position,
            )
            for name, kind, position in (
                ("1 DIA", "open", 1024),
                ("PERDIDO", "lost", 2048),
            )
        ]
    return fid, stages


async def principal():
    async with connection() as conn:
        card = await conn.fetchrow("SELECT * FROM kb_cards WHERE account_id=1")
        stages = await conn.fetch(
            "SELECT id,kind FROM kb_stages WHERE account_id=1 AND funnel_id=$1 "
            "ORDER BY position",
            card["funnel_id"],
        )
    return card, {s["kind"]: s["id"] for s in stages}


async def snapshot(card_id):
    async with connection() as conn:
        return await conn.fetchrow(
            "SELECT event_type,stage_kind FROM kb_card_events WHERE card_id=$1 "
            "ORDER BY created_at DESC,id DESC LIMIT 1",
            card_id,
        )


async def board(client, query="contact_id=10"):
    response = await client.get(f"/kanban/board?{query}")
    assert response.status_code == 200, response.text
    return response.json()["cards"]


async def test_keep_links_cards_and_preserves_origin(client):
    card, _ = await principal()
    fid, (day, _) = await follow_up()
    await client.patch(
        f"/kanban/cards/{card['id']}/value", json={"version": 1, "value_cents": 5000}
    )
    url = f"/kanban/cards/{card['id']}/transfer"
    body = {"version": 2, "funnel_id": fid, "stage_id": day}
    response = await client.post(url, json=body)
    assert response.status_code == 200, response.text
    created = response.json()
    assert created["origin_card_id"] == card["id"]
    assert created["origin_version"] == 3
    cards = {c["id"]: c for c in await board(client)}
    origin, destination = cards[card["id"]], cards[created["id"]]
    assert origin["stage_id"] == card["stage_id"]
    assert origin["transfer_card_id"] == created["id"]
    assert origin["transfer_funnel"] == "Follow up"
    assert destination["origin_card_id"] == card["id"]
    assert destination["origin_funnel"] == "Principal"
    assert destination["value_cents"] == 5000
    assert (await snapshot(card["id"]))["stage_kind"] == "open"
    # Repetir não duplica: a origem já tem destino aberto no funil.
    body["version"] = 3
    assert (await client.post(url, json=body)).status_code == 409
    async with connection() as conn:
        assert (await projection(conn, 1, 10))["kanban_etapa"] == "Follow up / 1 DIA"
        rows = await conn.fetch(
            "SELECT funnel_id,after_state->>'card_id' AS card FROM kb_history "
            "WHERE action='cartao_transferido' ORDER BY id"
        )
    assert [(r["funnel_id"], int(r["card"])) for r in rows] == [
        (card["funnel_id"], card["id"]),
        (fid, created["id"]),
    ]


async def test_close_hides_origin_outside_metrics(client):
    card, stages = await principal()
    fid, (day, _) = await follow_up()
    response = await client.post(
        f"/kanban/cards/{card['id']}/transfer",
        json={"version": 1, "funnel_id": fid, "stage_id": day, "origin_mode": "close"},
    )
    assert response.status_code == 200, response.text
    assert [c["id"] for c in await board(client)] == [response.json()["id"]]
    assert (await client.get(f"/kanban/cards/{card['id']}")).status_code == 200
    assert dict(await snapshot(card["id"])) == {
        "event_type": "transferred",
        "stage_kind": "transferred",
    }
    moved = await client.patch(
        f"/kanban/cards/{card['id']}", json={"version": 2, "stage_id": stages["won"]}
    )
    assert moved.status_code == 409
    # Reclassificar a etapa não devolve a origem aos abertos nas métricas.
    await client.put(
        f"/kanban/stages/{card['stage_id']}",
        json={"name": "Novo", "kind": "open", "position": 5000},
    )
    assert (await snapshot(card["id"]))["stage_kind"] == "transferred"
    summary = (await client.get("/kanban/metrics/summary")).json()["current"]
    # Só o destino segue em aberto; a origem não vira ganho nem perda.
    assert (summary["ongoing"], summary["wins"], summary["losses"]) == (1, 0, 0)


async def test_stage_mode_validates_loss_reason(client):
    card, stages = await principal()
    fid, (day, _) = await follow_up()
    url = f"/kanban/cards/{card['id']}/transfer"
    body = {
        "version": 1,
        "funnel_id": fid,
        "stage_id": day,
        "origin_mode": "stage",
        "origin_stage_id": stages["lost"],
    }
    assert (await client.post(url, json=body)).status_code == 422
    body["origin_lost_reason"] = "Sem retorno"
    assert (await client.post(url, json=body)).status_code == 200
    async with connection() as conn:
        origin = await conn.fetchrow("SELECT * FROM kb_cards WHERE id=$1", card["id"])
    assert origin["stage_id"] == stages["lost"]
    assert origin["lost_reason"] == "Sem retorno"
    assert origin["transferred_at"] is None


async def test_rejects_invalid_targets(client):
    card, stages = await principal()
    fid, (day, lost) = await follow_up()
    url = f"/kanban/cards/{card['id']}/transfer"
    same = {"version": 1, "funnel_id": card["funnel_id"], "stage_id": stages["won"]}
    assert (await client.post(url, json=same)).status_code == 422
    wrong_stage = {"version": 1, "funnel_id": fid, "stage_id": stages["won"]}
    assert (await client.post(url, json=wrong_stage)).status_code == 404
    no_reason = {"version": 1, "funnel_id": fid, "stage_id": lost}
    assert (await client.post(url, json=no_reason)).status_code == 422
    stray = {"version": 1, "funnel_id": fid, "stage_id": day, "origin_stage_id": day}
    assert (await client.post(url, json=stray)).status_code == 422
    async with connection() as conn:
        other = await conn.fetchval("SELECT id FROM kb_cards WHERE account_id=2")
    body = {"version": 1, "funnel_id": fid, "stage_id": day}
    assert (
        await client.post(f"/kanban/cards/{other}/transfer", json=body)
    ).status_code == 404
    async with connection() as conn:
        assert await conn.fetchval("SELECT count(*) FROM kb_cards") == 2


async def test_stage_batch_filters_idle_and_is_repeatable(client):
    card, _ = await principal()
    fid, (day, _) = await follow_up()
    async with connection() as conn:
        for contact in (11, 12):
            await conn.execute(
                "INSERT INTO kb_contacts(account_id,contact_id,name,last_activity_at) "
                "VALUES(1,$1,'Contato',now()-interval '5 days')",
                contact,
            )
            await conn.execute(
                "INSERT INTO kb_cards(account_id,contact_id,funnel_id,stage_id) "
                "VALUES(1,$1,$2,$3)",
                contact,
                card["funnel_id"],
                card["stage_id"],
            )
        await conn.execute(
            "UPDATE kb_cards SET stage_entered_at=now()-interval '5 days' "
            "WHERE account_id=1 AND contact_id IN (11,12)"
        )
        await conn.execute(
            "UPDATE kb_contacts SET last_activity_at=now() WHERE contact_id=10"
        )
    url = f"/kanban/stages/{card['stage_id']}/transfer"
    body = {"funnel_id": fid, "stage_id": day, "idle_days": 2}
    response = await client.post(url, json=body)
    assert response.status_code == 200, response.text
    result = response.json()
    assert result["transferred"] == 2
    assert result["remaining"] == 0
    assert all(r["ok"] for r in result["results"])
    again = (await client.post(url, json=body)).json()
    assert again == {"transferred": 0, "remaining": 0, "results": []}
    follow = await board(client, f"funnel_id={fid}")
    assert sorted(c["contact_id"] for c in follow) == [11, 12]


async def test_agent_sees_history_on_both_sides(client):
    card, _ = await principal()
    fid, (day, _) = await follow_up()
    async with connection() as conn:
        await conn.execute(
            "UPDATE kb_cards SET conversation_id=7,conversation_inbox_id=5 WHERE id=$1",
            card["id"],
        )
    app.dependency_overrides[identity] = lambda: {
        "account": 1,
        "id": 4,
        "name": "Agente",
        "role": "agent",
        "inboxes": [5],
    }
    response = await client.post(
        f"/kanban/cards/{card['id']}/transfer",
        json={"version": 1, "funnel_id": fid, "stage_id": day},
    )
    assert response.status_code == 200, response.text
    history = await client.get("/kanban/history?contact_id=10")
    assert history.status_code == 200, history.text
    actions = [h for h in history.json() if h["action"] == "cartao_transferido"]
    assert len(actions) == 2
