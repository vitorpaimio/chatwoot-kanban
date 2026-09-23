"""Métricas e exportação autenticadas, com período civil de Brasília."""

import csv
import io
from datetime import date, datetime, time, timedelta
from decimal import Decimal
from typing import Literal
from zoneinfo import ZoneInfo

import httpx
from fastapi import APIRouter, Depends, HTTPException, Query
from fastapi.encoders import jsonable_encoder
from fastapi.responses import Response
from pydantic import BaseModel, Field

from app.database import connection, notify
from app.metrics import queries
from app.metrics.service import native_options, service_data
from app.security import administrator, get_actor

router = APIRouter(prefix="/kanban/metrics")
AUTH = Depends(get_actor)
TZ = ZoneInfo("America/Sao_Paulo")
BLOCKS = Literal[
    "summary", "funnel", "losses", "sources", "service", "team", "tasks", "timeline"
]


def bounds(start=None, end=None):
    today = datetime.now(TZ).date()
    start, end = start or today.replace(day=1), end or today
    if end < start or (end - start).days > 365:
        raise HTTPException(
            422, "Escolha um período de até 366 dias, com início anterior ao fim."
        )
    return datetime.combine(start, time.min, TZ), datetime.combine(
        end + timedelta(days=1), time.min, TZ
    )


def comparison(current, previous):
    if current is None or previous is None:
        return None
    if not previous:
        return 0 if not current else None
    return float((current - previous) / abs(previous) * 100)


def compare_dict(current, previous):
    return {
        key: comparison(value, previous.get(key))
        for key, value in current.items()
        if isinstance(value, (int, float, Decimal)) or value is None
    }


def csv_response(block, payload):
    rows = []

    def flatten(value, prefix=""):
        if isinstance(value, dict):
            for key, child in value.items():
                flatten(child, f"{prefix}.{key}" if prefix else key)
        elif isinstance(value, list):
            for index, child in enumerate(value):
                flatten(child, f"{prefix}[{index}]")
        else:
            text = "" if value is None else str(value)
            if text.lstrip().startswith(("=", "+", "-", "@")):
                text = "'" + text
            rows.append([prefix, text])

    flatten(jsonable_encoder(payload))
    output = io.StringIO()
    writer = csv.writer(output, delimiter=";")
    writer.writerow(["campo", "valor"])
    writer.writerows(rows)
    return Response(
        "\ufeff" + output.getvalue(),
        media_type="text/csv; charset=utf-8",
        headers={"Content-Disposition": f'attachment; filename="metricas-{block}.csv"'},
    )


class Configuration(BaseModel):
    loss_reasons: list[str] = Field(min_length=0, max_length=50)


@router.get("/options")
async def options(user=AUTH):
    async with connection() as conn:
        funnels = await conn.fetch(
            (
                "SELECT id,name,stale_days FROM kb_funnels WHERE account_id=$"
                "1 ORDER BY position,id"
            ),
            user["account"],
        )
        reasons = await conn.fetchval(
            "SELECT loss_reasons FROM kb_accounts WHERE account_id=$1", user["account"]
        )
        temperature = await conn.fetchval(
            (
                "SELECT exists(SELECT 1 FROM kb_contacts WHERE account_id=$1 "
                "AND remote_attributes ? 'temperatura')"
            ),
            user["account"],
        )
        try:
            native = await native_options(conn, user["account"])
        except (httpx.HTTPError, ValueError):
            native = {
                "agents": [],
                "inboxes": [],
                "warning": "Não foi possível carregar os filtros do Chatwoot.",
            }
        return {
            **native,
            "funnels": [dict(r) for r in funnels],
            "loss_reasons": reasons or [],
            "temperature": temperature or native.get("temperature_declared", False),
        }


@router.get("/configuration")
async def configuration(user=AUTH):
    async with connection() as conn:
        return {
            "loss_reasons": await conn.fetchval(
                "SELECT loss_reasons FROM kb_accounts WHERE account_id=$1",
                user["account"],
            )
            or []
        }


@router.put("/configuration")
async def configure(body: Configuration, user=AUTH):
    administrator(user)
    reasons = list(
        dict.fromkeys(
            r.strip() for r in body.loss_reasons if r.strip() and r.strip() != "Outro"
        )
    )
    if any(len(r) > 120 for r in reasons):
        raise HTTPException(422, "Cada motivo deve ter até 120 caracteres.")
    async with connection() as conn:
        await conn.execute(
            "UPDATE kb_accounts SET loss_reasons=$2 WHERE account_id=$1",
            user["account"],
            reasons,
        )
        await notify(conn, user["account"])
    return {"loss_reasons": reasons}


async def calculate(conn, block, args):
    if block == "service":
        return await service_data(conn, args)
    sql = getattr(queries, block.upper())
    if block in ("summary", "tasks"):
        return dict(await conn.fetchrow(sql, *args))
    result = {"rows": [dict(r) for r in await conn.fetch(sql, *args)]}
    if block == "funnel":
        result["stale"] = [dict(r) for r in await conn.fetch(queries.STALE, *args)]
    if block == "sources":
        for dimension in ("origins", "campaigns"):
            result[dimension] = [
                dict(r)
                for r in await conn.fetch(getattr(queries, dimension.upper()), *args)
            ]
    if block == "timeline":
        result["temperature"] = [
            dict(r) for r in await conn.fetch(queries.TEMPERATURE, *args)
        ]
    return result


@router.get("/{block}")
async def metrics(
    block: BLOCKS,
    start: date | None = None,
    end: date | None = None,
    funnel_id: int | None = Query(None, gt=0),
    assignee_id: int | None = Query(None, gt=0),
    inbox_id: int | None = Query(None, gt=0),
    format: Literal["json", "csv"] = "json",
    user=AUTH,
):
    first, last = bounds(start, end)
    previous_start = first - (last - first)
    args = (user["account"], first, last, funnel_id, assignee_id, inbox_id)
    previous_args = (
        user["account"],
        previous_start,
        first,
        funnel_id,
        assignee_id,
        inbox_id,
    )
    async with connection() as conn:
        if funnel_id and not await conn.fetchval(
            "SELECT 1 FROM kb_funnels WHERE account_id=$1 AND id=$2",
            user["account"],
            funnel_id,
        ):
            raise HTTPException(404, "Funil não encontrado nesta conta")
        try:
            current = await calculate(conn, block, args)
            previous = await calculate(conn, block, previous_args)
        except (httpx.HTTPError, ValueError) as exc:
            raise HTTPException(
                503,
                (
                    "Atendimento temporariamente indisponível no Chatwoot; tente "
                    "novamente."
                ),
            ) from exc
        if block == "team":
            try:
                service = await service_data(conn, args)
                old_service = await service_data(conn, previous_args)
                for result, remote in ((current, service), (previous, old_service)):
                    by_agent = {
                        a["assignee_id"]: a["first_response_seconds"]
                        for a in remote["agents"]
                    }
                    for row in result["rows"]:
                        row["first_response_seconds"] = by_agent.get(row["assignee_id"])
            except (httpx.HTTPError, ValueError):
                current["warning"] = (
                    "Tempos de primeira resposta indisponíveis no Chatwoot."
                )
    result = {
        "current": current,
        "previous": previous,
        "variation": compare_dict(current, previous),
        "period": {
            "start": first.date(),
            "end": (last - timedelta(days=1)).date(),
            "previous_start": previous_start.date(),
            "previous_end": (first - timedelta(days=1)).date(),
            "timezone": str(TZ),
        },
    }
    if block == "service":
        for key in ("open", "unanswered"):
            result["variation"][key] = None
    return csv_response(block, result) if format == "csv" else result
