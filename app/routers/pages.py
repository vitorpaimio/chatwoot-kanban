"""Dados da página Tarefas do Pipeline (ADR-045)."""

from fastapi import APIRouter, Depends, Query
from fastapi.encoders import jsonable_encoder

from app.database import connection
from app.security import identity

AUTH = Depends(identity)
router = APIRouter(prefix="/kanban")

# Tarefa ativa de um contato visível, com a negociação do funil principal (ou a
# primeira ativa) para abrir no Kanban. A visibilidade vem de kb_visible_cards,
# a mesma regra de caixas do quadro.
VISIBLE_TASKS = """
WITH visible AS (
  SELECT t.id,t.contact_id,t.message AS descricao,t.due_date AS vencimento,
    t.due_state,t.assigned_to,a.name AS assignee_name,ct.name,ct.phone,ct.email,
    card.id AS card_id,card.funnel,card.stage,card.stage_color
  FROM kb_tasks t
  JOIN kb_contacts ct ON (ct.account_id,ct.contact_id)=(t.account_id,t.contact_id)
  JOIN LATERAL (
    SELECT c.id,f.name AS funnel,s.name AS stage,s.color AS stage_color
    FROM kb_visible_cards c
    JOIN kb_funnels f ON (f.account_id,f.id)=(c.account_id,c.funnel_id)
    JOIN kb_stages s ON (s.account_id,s.id)=(c.account_id,c.stage_id)
    WHERE c.account_id=t.account_id AND c.contact_id=t.contact_id AND NOT f.archived
    ORDER BY f.is_primary DESC,f.position,c.id LIMIT 1
  ) card ON true
  LEFT JOIN kb_agents a ON (a.account_id,a.user_id)=(t.account_id,t.assigned_to)
  WHERE t.account_id=$1 AND t.status='active'
)
"""


@router.get("/tasks")
async def tasks(
    user=AUTH,
    state: str = Query(default="", pattern="^(|overdue|today|active)$"),
    offset: int = Query(default=0, ge=0, le=100000),
    limit: int = Query(default=100, ge=1, le=200),
):
    """Tarefas ativas visíveis, da mais antiga para a mais distante."""
    async with connection(user) as conn:
        rows = await conn.fetch(
            VISIBLE_TASKS
            + """SELECT * FROM visible WHERE ($2='' OR due_state=$2)
            ORDER BY vencimento,lower(name),id LIMIT $3 OFFSET $4""",
            user["account"],
            state,
            limit,
            offset,
        )
        counts = await conn.fetchrow(
            VISIBLE_TASKS
            + """SELECT count(*) AS total,
              count(*) FILTER (WHERE due_state='overdue') AS overdue,
              count(*) FILTER (WHERE due_state='today') AS today,
              count(*) FILTER (WHERE due_state='active') AS active FROM visible""",
            user["account"],
        )
    return jsonable_encoder({"tasks": [dict(r) for r in rows], "counts": dict(counts)})
