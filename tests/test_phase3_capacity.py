"""Ensaio opt-in de capacidade local, com sessões controladas e PostgreSQL real."""

import asyncio
import json
import math
import os
import resource
import sys
import time
from collections import defaultdict
from pathlib import Path

import httpx
import pytest
from fastapi import Request

from app import database
from app.events import EventHub
from app.main import app
from app.routers import workspace
from app.security import identity

pytestmark = pytest.mark.skipif(
    not os.environ.get("PHASE3_LOAD_SECONDS"),
    reason="Defina PHASE3_LOAD_SECONDS=300 para executar o ensaio de capacidade",
)


def percentile(samples, fraction=0.95):
    ordered = sorted(samples)
    return ordered[max(0, math.ceil(len(ordered) * fraction) - 1)] if ordered else None


async def seed_capacity():
    funnels = {}
    async with database.connection() as conn, conn.transaction():
        for account in (1, 2):
            funnel = await conn.fetchval(
                "SELECT id FROM kb_funnels WHERE account_id=$1 AND is_primary", account
            )
            stages = await conn.fetch(
                "SELECT id FROM kb_stages WHERE account_id=$1 ORDER BY position",
                account,
            )
            stage_ids = [row["id"] for row in stages]
            funnels[account] = (funnel, stage_ids)
            await conn.execute(
                "INSERT INTO kb_agents(account_id,user_id,name,role) "
                "SELECT $1,n,'Pessoa '||n,CASE WHEN n%5=0 THEN 'administrator' "
                "ELSE 'agent' END FROM generate_series(100,114) n",
                account,
            )
            await conn.execute(
                "INSERT INTO kb_contacts(account_id,contact_id,name,phone,labels,"
                "assignee_id,assignee_name,conversation_id,inbox_id) "
                "SELECT $1,n,'Contato '||n,'5511'||n, '[\"capacidade\"]'::jsonb,"
                "100+n%15,'Pessoa '||(100+n%15),n,CASE WHEN n%2=0 THEN 11 "
                "ELSE 22 END FROM generate_series(100,20099) n",
                account,
            )
            await conn.execute(
                "INSERT INTO kb_cards(account_id,contact_id,funnel_id,stage_id,"
                "position,value_cents,created_by,conversation_id,"
                "conversation_inbox_id) "
                "SELECT $1,n,$2,($3::bigint[])[1+n%3],n*1024,n*100,100+n%15,n,"
                "CASE WHEN n%2=0 THEN 11 ELSE 22 END FROM generate_series(100,5099) n",
                account,
                funnel,
                stage_ids,
            )
            await conn.execute(
                "INSERT INTO kb_tasks(account_id,contact_id,message,due_date,"
                "created_by,assigned_to) SELECT $1,n,'Tarefa '||n,current_date,"
                "100+n%15,100+n%15 FROM generate_series(100,1099) n",
                account,
            )
        await conn.execute("ANALYZE")
    return funnels


async def test_phase3_capacity(db, monkeypatch):
    duration = float(os.environ["PHASE3_LOAD_SECONDS"])
    assert duration > 0
    funnels = await seed_capacity()
    users = [
        {
            "account": account,
            "id": number,
            "name": f"Pessoa {number}",
            "role": "administrator" if number % 5 == 0 else "agent",
            "inboxes": [11] if number % 2 == 0 else [22],
        }
        for account in (1, 2)
        for number in range(100, 115)
    ]

    async def controlled_identity(request: Request):
        return users[int(request.headers["x-capacity-session"])]

    async def controlled_stream_identity(request):
        return request.user

    app.dependency_overrides[identity] = controlled_identity
    monkeypatch.setattr(workspace, "identity", controlled_stream_identity)
    hub = EventHub()
    monkeypatch.setattr(workspace, "hub", hub)
    latencies = defaultdict(list)
    errors = []
    events = [0] * len(users)
    sent_at = [None] * len(users)
    confirmed = [asyncio.Event() for _ in users]
    streams = []
    consumers = []
    requests = defaultdict(int)
    maxima = {"pool": 0, "postgres_database": 0, "sync_backlog": 0}
    mutations = 0
    started = time.monotonic()
    deadline = started + duration

    class StreamRequest:
        def __init__(self, user):
            self.user = user

        async def is_disconnected(self):
            return False

    async def consume(index, stream):
        async for message in stream:
            if "event: change" in message:
                events[index] += 1
                if sent_at[index] is not None:
                    latencies["sse"].append((time.monotonic() - sent_at[index]) * 1000)
                    sent_at[index] = None
                confirmed[index].set()
            elif "event: expired" in message or "event: unavailable" in message:
                errors.append({"stream": index, "event": message.strip()})

    async def session_loop(index, client):
        user = users[index]
        funnel = funnels[user["account"]][0]
        paths = [
            ("board", f"/board?funnel_id={funnel}&limit=50"),
            ("board_filtered", f"/board?funnel_id={funnel}&limit=50&label=capacidade"),
            *(
                (f"metrics/{block}", f"/metrics/{block}?funnel_id={funnel}")
                for block in (
                    "summary",
                    "tasks",
                    "team",
                    "funnel",
                    "losses",
                    "sources",
                    "timeline",
                )
            ),
        ]
        iteration = 0
        while time.monotonic() < deadline:
            name, path = paths[iteration % len(paths)]
            began = time.monotonic()
            try:
                response = await client.get(
                    f"/kanban{path}&account={user['account']}",
                    headers={"x-capacity-session": str(index)},
                )
                requests[name] += 1
                latencies[name].append((time.monotonic() - began) * 1000)
                if response.status_code != 200:
                    errors.append({"route": name, "status": response.status_code})
                elif name.startswith("board"):
                    payload = response.json()
                    assert all(
                        c["account_id"] == user["account"] for c in payload["cards"]
                    )
                    counts = defaultdict(int)
                    for card in payload["cards"]:
                        counts[card["stage_id"]] += 1
                        assert user["role"] == "administrator" or (
                            card["conversation_inbox_id"] in user["inboxes"]
                            or (
                                card["conversation_id"] is None
                                and card["created_by"] == user["id"]
                            )
                        )
                    assert max(counts.values(), default=0) <= 50
            except Exception as error:
                errors.append({"route": name, "error": type(error).__name__})
            iteration += 1
            await asyncio.sleep(1)

    async def move_loop():
        nonlocal mutations
        while time.monotonic() < deadline:
            for index in range(15):
                confirmed[index].clear()
                sent_at[index] = time.monotonic()
            async with database.connection() as conn, conn.transaction():
                for contact in (100, 101):
                    await database.lock_contact(conn, 1, contact)
                    await conn.execute(
                        "UPDATE kb_cards SET version=version+1,stage_id=CASE "
                        "WHEN stage_id=$3 THEN $4 ELSE $3 END WHERE account_id=$1 "
                        "AND contact_id=$2",
                        1,
                        contact,
                        funnels[1][1][0],
                        funnels[1][1][1],
                    )
                    await database.record(
                        conn,
                        1,
                        contact,
                        users[0],
                        "cartao_movido",
                        after={"ensaio": True},
                        funnel=funnels[1][0],
                    )
                await database.notify(conn, 1)
            mutations += 1
            try:
                await asyncio.wait_for(
                    asyncio.gather(*(event.wait() for event in confirmed[:15])), 10
                )
            except TimeoutError:
                errors.append({"sse": "invalidação não recebida em 10 segundos"})
            await asyncio.sleep(min(2, max(0, deadline - time.monotonic())))

    async def monitor():
        while time.monotonic() < deadline:
            maxima["pool"] = max(maxima["pool"], database.pool.get_size())
            async with database.connection() as conn:
                connections = await conn.fetchval(
                    "SELECT count(*) FROM pg_stat_activity "
                    "WHERE datname=current_database()"
                )
                backlog = await conn.fetchval(
                    "SELECT count(*) FROM kb_sync WHERE status<>'synced'"
                )
            maxima["postgres_database"] = max(maxima["postgres_database"], connections)
            maxima["sync_backlog"] = max(maxima["sync_backlog"], backlog)
            await asyncio.sleep(min(1, max(0, deadline - time.monotonic())))

    try:
        for index, user in enumerate(users):
            response = await workspace.events(StreamRequest(user), user=user)
            stream = response.body_iterator
            streams.append(stream)
            assert "event: ready" in await anext(stream)
            consumers.append(asyncio.create_task(consume(index, stream)))
        assert hub.reserved == 30
        started = time.monotonic()
        deadline = started + duration
        async with httpx.AsyncClient(
            transport=httpx.ASGITransport(app=app),
            base_url="http://localhost:3000",
            timeout=30,
        ) as client:
            await asyncio.gather(
                *(session_loop(index, client) for index in range(30)),
                move_loop(),
                monitor(),
            )
    finally:
        for consumer in consumers:
            consumer.cancel()
        await asyncio.gather(*consumers, return_exceptions=True)
        for stream in streams:
            await stream.aclose()
        await hub.close()
        app.dependency_overrides.pop(identity, None)
    peak = resource.getrusage(resource.RUSAGE_SELF).ru_maxrss
    report = {
        "duration_seconds": time.monotonic() - started,
        "requested_seconds": duration,
        "think_time_seconds": 1,
        "scope": "ASGI local + PostgreSQL real exclusivo; 30 sessões controladas. "
        "Não mede autenticação Rails, HTTP real, navegador ou Chatwoot remoto. "
        "Métricas somente locais; worker não executado.",
        "seed": {
            "accounts": 2,
            "contacts_per_account": 20000,
            "cards_per_account": 5000,
            "tasks_per_account": 1000,
            "sessions_per_account": 15,
        },
        "latency_ms": {
            name: {
                "p95": percentile(values),
                "max": max(values),
                "samples": len(values),
            }
            for name, values in latencies.items()
        },
        "requests": dict(requests),
        "errors": errors,
        "sse_changes_by_session": events,
        "mutations": mutations,
        "max_connections": maxima,
        "process_peak_rss_bytes": peak if sys.platform == "darwin" else peak * 1024,
        "sse_reservations_after_cleanup": hub.reserved,
        "targets_ms": {"board": 500, "metrics": 1000, "sse": 2000},
    }
    Path("docs/phase3-capacity.json").write_text(
        json.dumps(report, indent=2, ensure_ascii=False) + "\n"
    )
    assert not errors, errors[:10]
    assert not any(events[15:]), "Conta não afetada recebeu invalidação"
    assert all(events[:15]), "Alguma sessão afetada não recebeu invalidação"
    assert hub.reserved == 0 and not hub.subscribers
    assert maxima["pool"] <= 10
    assert maxima["sync_backlog"] <= 2
    assert percentile(latencies["board"]) <= 500
    assert percentile(latencies["board_filtered"]) <= 500
    for name, values in latencies.items():
        if name.startswith("metrics/"):
            assert percentile(values) <= 1000, name
    assert percentile(latencies["sse"]) <= 2000
