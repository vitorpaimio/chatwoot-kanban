"""Página Tarefas: lista de tarefas visíveis (ADR-045)."""

from app.database import connection
from app.main import app
from app.security import identity

AGENT = {"account": 1, "id": 4, "name": "Agente", "role": "agent", "inboxes": [11]}


async def test_tasks_list_state_counts_and_card(client):
    async with connection() as conn:
        await conn.execute(
            """INSERT INTO kb_agents(account_id,user_id,name,role)
            VALUES(1,3,'Administrador','administrator')"""
        )
        await conn.execute(
            """INSERT INTO kb_tasks(account_id,contact_id,message,due_date,due_state,
            assigned_to) VALUES(1,10,'Ligar para Maria',current_date-1,'overdue',3)"""
        )
        # Tarefa de outra conta não aparece.
        await conn.execute(
            """INSERT INTO kb_tasks(account_id,contact_id,message,due_date,due_state)
            VALUES(2,10,'Outra conta',current_date,'today')"""
        )
    response = await client.get("/kanban/tasks?account=1")
    assert response.status_code == 200
    body = response.json()
    assert body["counts"] == {"total": 1, "overdue": 1, "today": 0, "active": 0}
    [task] = body["tasks"]
    assert task["descricao"] == "Ligar para Maria"
    assert task["name"] == "Maria"
    assert task["due_state"] == "overdue"
    assert task["assignee_name"] == "Administrador"
    assert (task["funnel"], task["stage"]) == ("Principal", "Novo")
    assert task["card_id"]
    today = await client.get("/kanban/tasks?account=1&state=today")
    assert today.json()["tasks"] == []
    invalid = await client.get("/kanban/tasks?account=1&state=vencida")
    assert invalid.status_code == 422


async def test_tasks_follow_card_visibility(client):
    async with connection() as conn:
        await conn.execute(
            """INSERT INTO kb_tasks(account_id,contact_id,message,due_date)
            VALUES(1,10,'Tarefa restrita',current_date+3)"""
        )
        # Negociação ligada a uma conversa de caixa fora do alcance do agente.
        await conn.execute(
            """UPDATE kb_cards SET conversation_id=100,conversation_inbox_id=22,
            created_by=3 WHERE account_id=1"""
        )
    app.dependency_overrides[identity] = lambda: dict(AGENT)
    hidden = await client.get("/kanban/tasks?account=1")
    assert hidden.json() == {
        "tasks": [],
        "counts": {"total": 0, "overdue": 0, "today": 0, "active": 0},
    }
    async with connection() as conn:
        await conn.execute(
            "UPDATE kb_cards SET conversation_inbox_id=11 WHERE account_id=1"
        )
    visible = await client.get("/kanban/tasks?account=1")
    assert [t["descricao"] for t in visible.json()["tasks"]] == ["Tarefa restrita"]


async def test_tasks_require_enabled_account(client):
    async with connection() as conn:
        await conn.execute("UPDATE kb_accounts SET enabled=false WHERE account_id=1")
    response = await client.get("/kanban/tasks?account=1")
    assert response.status_code == 403
