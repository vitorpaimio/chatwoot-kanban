import asyncio
import contextlib
import hashlib
import hmac
import json
import time
from datetime import date
from decimal import Decimal
from typing import Annotated

import httpx
from fastapi import APIRouter, Depends, HTTPException, Query, Request
from fastapi.encoders import jsonable_encoder
from pydantic import BaseModel, ConfigDict, Field

from app.board import board_page
from app.chatwoot_client import Chatwoot
from app.config import settings
from app.database import connection, lock_contact, notify, record
from app.event_response import EventResponse
from app.events import hub
from app.reporting import evolution
from app.routers.provisioning import configuration_lock
from app.security import administrator, decrypt, encrypt, identity
from app.services import refresh_contact, task_state

AUTH = Depends(identity)

router = APIRouter(prefix="/kanban")


class Input(BaseModel):
    model_config = ConfigDict(str_strip_whitespace=True, extra="forbid")


class Activation(Input):
    token: str = Field(min_length=10)


class Funnel(Input):
    name: str = Field(min_length=1, max_length=100)
    position: Decimal = Decimal(1024)
    stale_days: int = Field(default=7, ge=1, le=365)


class FunnelSettings(Funnel):
    auto_create: bool = False
    auto_create_stage_id: int | None = Field(default=None, gt=0)
    auto_create_inboxes: list[Annotated[int, Field(gt=0)]] = Field(
        default_factory=list, max_length=500
    )


class Stage(Funnel):
    color: str = Field(default="#6366f1", pattern=r"^#[a-fA-F0-9]{6}$")
    kind: str = Field(default="open", pattern="^(open|won|lost)$")


class Archive(Input):
    destination_id: int | None = None


class Card(Input):
    lost_reason: str | None = Field(default=None, min_length=1, max_length=500)
    contact_id: int = Field(gt=0)
    funnel_id: int = Field(gt=0)
    stage_id: int = Field(gt=0)


class Move(Input):
    lost_reason: str | None = Field(default=None, min_length=1, max_length=500)
    version: int = Field(gt=0)
    stage_id: int = Field(gt=0)
    before_id: int | None = None
    value_cents: int | None = Field(default=None, ge=0, le=999_999_999_99)


class Task(Input):
    descricao: str = Field(min_length=1, max_length=4000)
    vencimento: date
    assigned_to: int | None = Field(default=None, gt=0)
    version: int | None = None


class Version(Input):
    version: int = Field(gt=0)


async def agent(conn, user):
    exists = await conn.fetchval(
        "SELECT 1 FROM kb_accounts WHERE account_id=$1", user["account"]
    )
    if not exists:
        raise HTTPException(409, "Ative esta conta antes de usar o Kanban")
    await conn.execute(
        (
            """
        INSERT INTO kb_agents(account_id,user_id,name,role)
        VALUES($1,$2,$3,$4) ON CONFLICT(account_id,user_id) DO UPDATE SET
        name=excluded.name,role=excluded.role
        """
        ),
        user["account"],
        user["id"],
        user["name"],
        user["role"],
    )


def require(row):
    if not row:
        raise HTTPException(404, "Registro não encontrado nesta conta")
    return row


@router.get("/session")
async def session(user=AUTH):
    async with connection() as conn:
        account = await conn.fetchrow(
            (
                """
        SELECT enabled,activation_status,activation_error,imported_count,
        import_status,import_error,provisioning_warnings FROM
        kb_accounts WHERE account_id=$1
        """
            ),
            user["account"],
        )
    return {**user, "activation": dict(account) if account else None}


@router.post("/activate")
async def activate(body: Activation, user=AUTH):
    administrator(user)
    try:
        async with Chatwoot(user["account"], body.token) as cw:
            await cw.request("GET", "/webhooks")
    except httpx.HTTPError:
        raise HTTPException(400, "Token sem acesso administrativo à conta") from None
    async with connection() as conn, conn.transaction():
        await configuration_lock(conn, user["account"])
        await conn.execute(
            (
                """
        INSERT INTO kb_accounts(account_id,token_cipher,attribute_mappings)
        VALUES($1,$2,'{"origem":null,"campanha":null,"temperatura":null}') ON
        CONFLICT(account_id) DO UPDATE SET token_cipher=excluded.token_cipher,
        activation_status= 'pending' ,activation_error=NULL,enabled=true,
        activation_next_attempt=now(),activation_attempts=0,remote_next_attempt=now()
        """
            ),
            user["account"],
            encrypt(body.token),
        )
        await notify(conn, user["account"])
    return {"status": "pending"}


class Enabled(Input):
    enabled: bool


@router.put("/activation")
async def set_activation(body: Enabled, user=AUTH):
    administrator(user)
    async with connection() as conn, conn.transaction():
        require(
            await conn.fetchval(
                "UPDATE kb_accounts SET enabled=$2 WHERE account_id=$1 "
                "RETURNING account_id",
                user["account"],
                body.enabled,
            )
        )
        await notify(conn, user["account"])
    return {"enabled": body.enabled}


@router.get("/board")
async def board(
    user=AUTH,
    funnel_id: int | None = None,
    stage_id: int | None = None,
    contact_id: int | None = None,
    search: str = Query(default="", max_length=200),
    assignee_id: int | None = None,
    label: str = Query(default="", max_length=200),
    task: str = Query(default="", pattern="^(|none|active|today|overdue)$"),
    offset: int = Query(default=0, ge=0, le=100000),
    limit: int = Query(default=50, ge=1, le=100),
):
    async with connection(user) as conn:
        return await board_page(
            conn,
            user["account"],
            funnel_id,
            stage_id,
            contact_id,
            search,
            assignee_id,
            label,
            task,
            offset,
            limit,
        )


async def automation_stage(conn, account, funnel_id, body: FunnelSettings):
    """Valida a etapa de entrada; sem escolha, usa a primeira etapa aberta."""
    if not body.auto_create:
        return None
    stage = await conn.fetchval(
        """SELECT id FROM kb_stages WHERE account_id=$1 AND funnel_id=$2
        AND NOT archived AND kind='open' AND ($3::bigint IS NULL OR id=$3)
        ORDER BY position,id LIMIT 1""",
        account,
        funnel_id,
        body.auto_create_stage_id,
    )
    if not stage:
        raise HTTPException(
            422, "Escolha uma etapa em andamento deste funil para a criação automática"
        )
    return stage


async def disable_automation(conn, account, stage_id):
    """Etapa arquivada ou encerrada deixa de receber novos leads."""
    await conn.execute(
        """UPDATE kb_funnels SET auto_create_stage_id=NULL WHERE account_id=$1
        AND auto_create_stage_id=$2""",
        account,
        stage_id,
    )


@router.get("/inboxes")
async def inboxes(user=AUTH):
    administrator(user)
    async with connection(user) as conn:
        await agent(conn, user)
        try:
            async with await Chatwoot.for_account(conn, user["account"]) as cw:
                result = await cw.request("GET", "/inboxes")
        except httpx.HTTPError:
            raise HTTPException(
                502, "Não foi possível consultar as caixas de entrada no Chatwoot"
            ) from None
    return [
        {"id": row["id"], "name": row["name"], "channel_type": row.get("channel_type")}
        for row in result.get("payload", [])
    ]


@router.post("/funnels")
async def create_funnel(body: FunnelSettings, user=AUTH):
    administrator(user)
    async with connection(user) as conn, conn.transaction():
        await agent(conn, user)
        fid = await conn.fetchval(
            (
                """
        INSERT INTO kb_funnels(account_id,name,position,stale_days) VALUES($1,$2,$3,$4)
        RETURNING id
        """
            ),
            user["account"],
            body.name,
            body.position,
            body.stale_days,
        )
        await conn.execute(
            """
        INSERT INTO kb_stages(account_id,funnel_id,name) VALUES($1,$2, 'Novo'
        )
        """,
            user["account"],
            fid,
        )
        await conn.execute(
            """UPDATE kb_funnels SET auto_create_stage_id=$3,auto_create_inboxes=$4
            WHERE account_id=$1 AND id=$2""",
            user["account"],
            fid,
            await automation_stage(conn, user["account"], fid, body),
            sorted(set(body.auto_create_inboxes)),
        )
        await record(
            conn,
            user["account"],
            None,
            user,
            "funil_criado",
            after=body.model_dump(mode="json"),
            funnel=fid,
            sync=False,
        )
    return {"id": fid}


@router.put("/funnels/{funnel_id}")
async def edit_funnel(funnel_id: int, body: FunnelSettings, user=AUTH):
    administrator(user)
    async with connection(user) as conn, conn.transaction():
        stage = await automation_stage(conn, user["account"], funnel_id, body)
        require(
            await conn.fetchval(
                (
                    """
        UPDATE kb_funnels SET name=$3,position=$4,stale_days=$5,
        auto_create_stage_id=$6,auto_create_inboxes=$7 WHERE account_id=$1 AND
        id=$2 AND NOT archived RETURNING id
        """
                ),
                user["account"],
                funnel_id,
                body.name,
                body.position,
                body.stale_days,
                stage,
                sorted(set(body.auto_create_inboxes)),
            )
        )
        await record(
            conn,
            user["account"],
            None,
            user,
            "funil_editado",
            after=body.model_dump(mode="json"),
            funnel=funnel_id,
            sync=False,
        )
        await queue_funnel(conn, user, funnel_id)
    return {"ok": True}


async def queue_funnel(conn, user, funnel):
    contacts = await conn.fetch(
        (
            """
        SELECT contact_id FROM kb_visible_cards WHERE account_id=$1 AND funnel_id=$2
        ORDER BY contact_id
        """
        ),
        user["account"],
        funnel,
    )
    for row in contacts:
        await lock_contact(conn, user["account"], row["contact_id"])
        await record(
            conn,
            user["account"],
            row["contact_id"],
            user,
            "configuracao_atualizada",
            funnel=funnel,
        )


@router.post("/funnels/{funnel_id}/archive")
async def archive_funnel(funnel_id: int, user=AUTH):
    administrator(user)
    async with connection(user) as conn, conn.transaction():
        row = require(
            await conn.fetchrow(
                """
        SELECT * FROM kb_funnels WHERE account_id=$1 AND id=$2 FOR UPDATE
        """,
                user["account"],
                funnel_id,
            )
        )
        if row["is_primary"]:
            raise HTTPException(409, "O Funil principal deve permanecer ativo")
        await conn.execute(
            """
        UPDATE kb_funnels SET archived=true WHERE account_id=$1 AND id=$2
        """,
            user["account"],
            funnel_id,
        )
        await record(
            conn,
            user["account"],
            None,
            user,
            "funil_arquivado",
            funnel=funnel_id,
            sync=False,
        )
        await queue_funnel(conn, user, funnel_id)
    return {"ok": True}


@router.post("/funnels/{funnel_id}/stages")
async def create_stage(funnel_id: int, body: Stage, user=AUTH):
    administrator(user)
    async with connection(user) as conn, conn.transaction():
        require(
            await conn.fetchval(
                (
                    """
        SELECT id FROM kb_funnels WHERE account_id=$1 AND id=$2 AND NOT
        archived
        """
                ),
                user["account"],
                funnel_id,
            )
        )
        sid = await conn.fetchval(
            (
                """
        INSERT INTO kb_stages(account_id,funnel_id,name,color,kind,position)
        VALUES($1,$2,$3,$4,$5,$6) RETURNING id
        """
            ),
            user["account"],
            funnel_id,
            body.name,
            body.color,
            body.kind,
            body.position,
        )
        await record(
            conn,
            user["account"],
            None,
            user,
            "etapa_criada",
            after=body.model_dump(mode="json"),
            funnel=funnel_id,
            stage=sid,
            sync=False,
        )
    return {"id": sid}


@router.put("/stages/{stage_id}")
async def edit_stage(stage_id: int, body: Stage, user=AUTH):
    administrator(user)
    async with connection(user) as conn, conn.transaction():
        row = require(
            await conn.fetchrow(
                (
                    """
        UPDATE kb_stages SET name=$3,color=$4,kind=$5,position=$6 WHERE
        account_id=$1 AND id=$2 AND NOT archived RETURNING funnel_id
        """
                ),
                user["account"],
                stage_id,
                body.name,
                body.color,
                body.kind,
                body.position,
            )
        )
        if body.kind != "open":
            await disable_automation(conn, user["account"], stage_id)
        await record(
            conn,
            user["account"],
            None,
            user,
            "etapa_editada",
            after=body.model_dump(mode="json"),
            funnel=row["funnel_id"],
            stage=stage_id,
            sync=False,
        )
        await queue_funnel(conn, user, row["funnel_id"])
    return {"ok": True}


@router.post("/stages/{stage_id}/archive")
async def archive_stage(stage_id: int, body: Archive, user=AUTH):
    administrator(user)
    account = user["account"]
    async with connection(user) as conn, conn.transaction():
        stage = require(
            await conn.fetchrow(
                """
        SELECT * FROM kb_stages WHERE account_id=$1 AND id=$2 AND NOT archived
        """,
                account,
                stage_id,
            )
        )
        await conn.execute(
            """
        SELECT id FROM kb_funnels WHERE account_id=$1 AND id=$2 FOR UPDATE
        """,
            account,
            stage["funnel_id"],
        )
        count = await conn.fetchval(
            (
                """
        SELECT count(*) FROM kb_stages WHERE account_id=$1 AND funnel_id=$2
        AND NOT archived
        """
            ),
            account,
            stage["funnel_id"],
        )
        if count < 2:
            raise HTTPException(409, "Mantenha pelo menos uma etapa no funil")
        cards = await conn.fetch(
            (
                """
        SELECT * FROM kb_visible_cards WHERE account_id=$1 AND stage_id=$2 ORDER BY
        contact_id
        """
            ),
            account,
            stage_id,
        )
        if cards:
            if body.destination_id is None:
                raise HTTPException(409, "Escolha uma etapa de destino para os cartões")
            destination = require(
                await conn.fetchrow(
                    (
                        """
        SELECT * FROM kb_stages WHERE account_id=$1 AND id=$2 AND NOT archived
        """
                    ),
                    account,
                    body.destination_id,
                )
            )
            if (
                destination["funnel_id"] != stage["funnel_id"]
                or destination["id"] == stage_id
            ):
                raise HTTPException(409, "Escolha outra etapa deste funil")
            for card in cards:
                await lock_contact(conn, account, card["contact_id"])
                await conn.execute(
                    (
                        """
        UPDATE kb_cards SET
        stage_id=$3,version=version+1,stage_entered_at=now() WHERE
        account_id=$1 AND id=$2
        """
                    ),
                    account,
                    card["id"],
                    destination["id"],
                )
                await record(
                    conn,
                    account,
                    card["contact_id"],
                    user,
                    "etapa_arquivada_movimento",
                    {"stage_id": stage_id},
                    {"stage_id": destination["id"]},
                    stage["funnel_id"],
                    destination["id"],
                )
        await conn.execute(
            "UPDATE kb_stages SET archived=true WHERE account_id=$1 AND id=$2",
            account,
            stage_id,
        )
        await disable_automation(conn, account, stage_id)
        await record(
            conn,
            account,
            None,
            user,
            "etapa_arquivada",
            funnel=stage["funnel_id"],
            stage=stage_id,
            sync=False,
        )
    return {"ok": True}


async def validate_loss(conn, account, stage_id, reason):
    kind = await conn.fetchval(
        "SELECT kind FROM kb_stages WHERE account_id=$1 AND id=$2", account, stage_id
    )
    if kind != "lost":
        return None
    reasons = await conn.fetchval(
        "SELECT loss_reasons FROM kb_accounts WHERE account_id=$1", account
    )
    if not reason or (
        reason not in reasons
        and not (reason.startswith("Outro: ") and reason[7:].strip())
    ):
        raise HTTPException(
            422, "Informe um motivo de perda válido ou Outro com uma descrição."
        )
    return reason


@router.post("/cards")
async def create_card(body: Card, user=AUTH):
    account = user["account"]
    async with connection(user) as conn, conn.transaction():
        require(
            await conn.fetchval(
                (
                    """
        SELECT id FROM kb_funnels WHERE account_id=$1 AND id=$2 AND NOT
        archived FOR UPDATE
        """
                ),
                account,
                body.funnel_id,
            )
        )
        require(
            await conn.fetchval(
                (
                    """
        SELECT id FROM kb_stages WHERE account_id=$1 AND funnel_id=$2 AND
        id=$3 AND NOT archived
        """
                ),
                account,
                body.funnel_id,
                body.stage_id,
            )
        )
        loss_reason = await validate_loss(
            conn, account, body.stage_id, body.lost_reason
        )
        await lock_contact(conn, account, body.contact_id)
        exists = await conn.fetchval(
            "SELECT 1 FROM kb_contacts WHERE account_id=$1 AND contact_id=$2",
            account,
            body.contact_id,
        )
        if not exists:
            async with await Chatwoot.for_account(conn, account) as cw:
                try:
                    await refresh_contact(
                        conn, cw, body.contact_id, project_cards=False
                    )
                except httpx.HTTPStatusError as exc:
                    if exc.response.status_code == 404:
                        raise HTTPException(
                            404, "Contato não encontrado nesta conta"
                        ) from exc
                    raise HTTPException(
                        502, "Não foi possível consultar o contato no Chatwoot"
                    ) from exc
        linked = await conn.fetchrow(
            "SELECT conversation_id,inbox_id FROM kb_contacts WHERE "
            "account_id=$1 AND contact_id=$2",
            account,
            body.contact_id,
        )
        if (
            user["role"] != "administrator"
            and linked["conversation_id"]
            and linked["inbox_id"] not in user.get("inboxes", [])
        ):
            raise HTTPException(404, "Registro não encontrado nesta conta")
        cid = await conn.fetchval(
            (
                """
        INSERT INTO kb_cards(account_id,contact_id,funnel_id,stage_id,lost_reason,
        created_by,conversation_id,conversation_inbox_id)
        SELECT $1,$2,$3,$4,$5,$6,conversation_id,inbox_id FROM kb_contacts
        WHERE account_id=$1 AND contact_id=$2 RETURNING id
        """
            ),
            account,
            body.contact_id,
            body.funnel_id,
            body.stage_id,
            loss_reason,
            user["id"],
        )
        await record(
            conn,
            account,
            body.contact_id,
            user,
            "cartao_criado",
            after={"card_id": cid, "lost_reason": loss_reason},
            funnel=body.funnel_id,
            stage=body.stage_id,
        )
    return {"id": cid}


async def move_card(conn, card_id, body, user):
    account = user["account"]
    card = require(
        await conn.fetchrow(
            "SELECT * FROM kb_visible_cards WHERE account_id=$1 AND id=$2",
            account,
            card_id,
        )
    )
    require(
        await conn.fetchval(
            (
                """
        SELECT id FROM kb_funnels WHERE account_id=$1 AND id=$2 AND NOT
        archived FOR UPDATE
        """
            ),
            account,
            card["funnel_id"],
        )
    )
    await lock_contact(conn, account, card["contact_id"])
    card = require(
        await conn.fetchrow(
            "SELECT * FROM kb_visible_cards WHERE account_id=$1 AND id=$2",
            account,
            card_id,
        )
    )
    if card["version"] != body.version:
        raise HTTPException(409, "Cartão alterado por outra pessoa. Atualize o quadro.")
    require(
        await conn.fetchval(
            (
                """
        SELECT id FROM kb_stages WHERE account_id=$1 AND funnel_id=$2 AND
        id=$3 AND NOT archived
        """
            ),
            account,
            card["funnel_id"],
            body.stage_id,
        )
    )
    loss_reason = card["lost_reason"]
    if body.stage_id != card["stage_id"]:
        loss_reason = await validate_loss(
            conn, account, body.stage_id, body.lost_reason
        )
    ordered = await conn.fetch(
        (
            """
        SELECT id,position FROM kb_visible_cards WHERE account_id=$1 AND stage_id=$2
        AND id<>$3 ORDER BY position,id
        """
        ),
        account,
        body.stage_id,
        card_id,
    )
    ids = [r["id"] for r in ordered]
    if body.before_id is not None and body.before_id not in ids:
        raise HTTPException(404, "Registro não encontrado nesta conta")
    index = ids.index(body.before_id) if body.before_id else len(ids)
    left = ordered[index - 1]["position"] if index else Decimal(0)
    right = ordered[index]["position"] if index < len(ordered) else left + 2048
    position = (left + right) / 2
    if right - left < Decimal("0.000001"):
        for i, row in enumerate(ordered):
            await conn.execute(
                "UPDATE kb_cards SET position=$3 WHERE account_id=$1 AND id=$2",
                account,
                row["id"],
                Decimal((i + 1) * 1024),
            )
        position = Decimal(index * 1024 + 512)
    value = body.value_cents if body.value_cents is not None else card["value_cents"]
    await conn.execute(
        (
            """
        UPDATE kb_cards SET
        stage_id=$3,position=$4,value_cents=$5,lost_reason=$6,version=version+1,
        stage_entered_at=CASE WHEN stage_id<>$3 THEN now() ELSE
        stage_entered_at END WHERE account_id=$1 AND id=$2
        """
        ),
        account,
        card_id,
        body.stage_id,
        position,
        value,
        loss_reason,
    )
    await conn.execute(
        """
        UPDATE kb_contacts SET last_card_id=$3 WHERE account_id=$1 AND
        contact_id=$2
        """,
        account,
        card["contact_id"],
        card_id,
    )
    await record(
        conn,
        account,
        card["contact_id"],
        user,
        "cartao_movido",
        {
            "stage_id": card["stage_id"],
            "value_cents": card["value_cents"],
            "entered_at": card["stage_entered_at"].isoformat(),
        },
        {
            "card_id": card_id,
            "stage_id": body.stage_id,
            "value_cents": value,
            "lost_reason": loss_reason,
        },
        card["funnel_id"],
        body.stage_id,
    )


@router.get("/cards/{card_id}")
async def get_card(card_id: int, user=AUTH):
    async with connection(user) as conn:
        page = await board_page(
            conn,
            user["account"],
            None,
            None,
            None,
            "",
            None,
            "",
            "",
            0,
            1,
            card_id=card_id,
        )
        return require(page["cards"])[0]


@router.get("/contacts/{contact_id}/task")
async def get_task(contact_id: int, user=AUTH):
    async with connection(user) as conn:
        require(
            await conn.fetchval(
                "SELECT contact_id FROM kb_contacts "
                "WHERE account_id=$1 AND contact_id=$2",
                user["account"],
                contact_id,
            )
        )
        task = await conn.fetchrow(
            """SELECT id,message AS descricao,due_date AS vencimento,version,assigned_to
            FROM kb_tasks WHERE account_id=$1 AND contact_id=$2 AND status='active'""",
            user["account"],
            contact_id,
        )
        return dict(task) if task else None


async def change_card_deletion(card_id: int, body: Version, user, deleted: bool):
    """Exclui/restaura uma negociação autorizada na transação do contato."""
    async with connection(user) as conn:
        card = require(
            await conn.fetchrow(
                "SELECT * FROM kb_authorized_cards WHERE account_id=$1 AND id=$2",
                user["account"],
                card_id,
            )
        )
        await lock_contact(conn, user["account"], card["contact_id"])
        card = require(
            await conn.fetchrow(
                "SELECT * FROM kb_authorized_cards WHERE account_id=$1 AND id=$2",
                user["account"],
                card_id,
            )
        )
        if card["version"] != body.version:
            raise HTTPException(409, "Negociação alterada; atualize o quadro")
        if deleted:
            await conn.execute(
                "INSERT INTO kb_card_deletions(account_id,card_id) VALUES($1,$2) "
                "ON CONFLICT DO NOTHING",
                user["account"],
                card_id,
            )
        else:
            await conn.execute(
                "DELETE FROM kb_card_deletions WHERE account_id=$1 AND card_id=$2",
                user["account"],
                card_id,
            )
        version = await conn.fetchval(
            "UPDATE kb_cards SET version=version+1 WHERE account_id=$1 AND id=$2 "
            "RETURNING version",
            user["account"],
            card_id,
        )
        await record(
            conn,
            user["account"],
            card["contact_id"],
            user,
            "negociacao_excluida" if deleted else "negociacao_restaurada",
            after={"card_id": card_id},
            funnel=card["funnel_id"],
        )
        return {"version": version}


@router.delete("/cards/{card_id}")
async def delete_card(card_id: int, body: Version, user=AUTH):
    return await change_card_deletion(card_id, body, user, True)


@router.post("/cards/{card_id}/restore")
async def restore_card(card_id: int, body: Version, user=AUTH):
    return await change_card_deletion(card_id, body, user, False)


@router.patch("/cards/{card_id}")
async def move(card_id: int, body: Move, user=AUTH):
    async with connection(user) as conn, conn.transaction():
        await move_card(conn, card_id, body, user)
    return {"ok": True}


class ConversationLink(Input):
    conversation_id: int | None = Field(default=None, gt=0)
    version: int = Field(gt=0)


@router.get("/cards/{card_id}/conversations")
async def conversation_options(card_id: int, user=AUTH):
    """Lista conversas do contato somente nas caixas autorizadas."""
    async with connection(user) as conn:
        card = require(
            await conn.fetchrow(
                "SELECT contact_id FROM kb_visible_cards WHERE account_id=$1 AND id=$2",
                user["account"],
                card_id,
            )
        )
        async with await Chatwoot.for_account(conn, user["account"]) as cw:
            response = await cw.request(
                "GET", f"/contacts/{card['contact_id']}/conversations"
            )
        result = []
        for conversation in response.get("payload", []):
            if user["role"] != "administrator" and conversation.get(
                "inbox_id"
            ) not in user.get("inboxes", []):
                continue
            messages = conversation.get("messages") or []
            message = messages[-1] if messages else {}
            result.append(
                {
                    "id": conversation["id"],
                    "inbox": (conversation.get("inbox") or {}).get("name")
                    or f"Caixa {conversation.get('inbox_id', '')}",
                    "status": conversation.get("status", ""),
                    "preview": (message.get("content") or "Sem mensagem de texto")[
                        :250
                    ],
                    "last_activity_at": conversation.get("last_activity_at"),
                }
            )
        return sorted(
            result, key=lambda c: (c["last_activity_at"] or 0, c["id"]), reverse=True
        )


@router.put("/cards/{card_id}/conversation")
async def link_conversation(card_id: int, body: ConversationLink, user=AUTH):
    async with connection(user) as conn:
        card = require(
            await conn.fetchrow(
                "SELECT * FROM kb_visible_cards WHERE account_id=$1 AND id=$2",
                user["account"],
                card_id,
            )
        )
        await lock_contact(conn, user["account"], card["contact_id"])
        card = require(
            await conn.fetchrow(
                "SELECT * FROM kb_visible_cards WHERE account_id=$1 AND id=$2",
                user["account"],
                card_id,
            )
        )
        if card["version"] != body.version:
            raise HTTPException(409, "Cartão alterado; atualize o quadro")
        async with await Chatwoot.for_account(conn, user["account"]) as cw:
            response = await cw.request(
                "GET", f"/contacts/{card['contact_id']}/conversations"
            )
        conversations = response.get("payload", [])
        linked = (
            next((c for c in conversations if c["id"] == body.conversation_id), None)
            if body.conversation_id
            else max(
                conversations,
                key=lambda c: (c.get("last_activity_at") or 0, c["id"]),
                default={},
            )
        )
        if body.conversation_id and not linked:
            raise HTTPException(404, "Registro não encontrado nesta conta")
        if (
            linked
            and user["role"] != "administrator"
            and linked.get("inbox_id") not in user.get("inboxes", [])
        ):
            raise HTTPException(404, "Registro não encontrado nesta conta")
        await conn.execute(
            """UPDATE kb_cards SET conversation_id=$3,conversation_inbox_id=$4,
            conversation_pinned=$5,version=version+1 WHERE account_id=$1 AND id=$2""",
            user["account"],
            card_id,
            linked.get("id"),
            linked.get("inbox_id"),
            body.conversation_id is not None,
        )
        await record(
            conn,
            user["account"],
            card["contact_id"],
            user,
            "conversa_vinculada",
            after={"card_id": card_id},
            funnel=card["funnel_id"],
            sync=False,
        )
    return {"ok": True}


@router.patch("/contacts/{contact_id}/stage")
async def legacy_move(
    contact_id: int, body: Move, funnel_id: int | None = None, user=AUTH
):
    async with connection(user) as conn, conn.transaction():
        cards = await conn.fetch(
            (
                """
        SELECT id FROM kb_visible_cards WHERE account_id=$1 AND contact_id=$2 AND
        ($3::bigint IS NULL OR funnel_id=$3)
        """
            ),
            user["account"],
            contact_id,
            funnel_id,
        )
        if not cards:
            raise HTTPException(404, "Registro não encontrado nesta conta")
        if len(cards) != 1:
            raise HTTPException(409, "Informe o funil ou mova pelo ID do cartão")
        await move_card(conn, cards[0]["id"], body, user)
    return {"ok": True}


@router.put("/contacts/{contact_id}/task")
async def save_task(contact_id: int, body: Task, user=AUTH):
    account = user["account"]
    async with connection(user) as conn, conn.transaction():
        await agent(conn, user)
        require(
            await conn.fetchval(
                (
                    """
        SELECT contact_id FROM kb_contacts WHERE account_id=$1 AND
        contact_id=$2
        """
                ),
                account,
                contact_id,
            )
        )
        await lock_contact(conn, account, contact_id)
        old = await conn.fetchrow(
            (
                """
        SELECT * FROM kb_tasks WHERE account_id=$1 AND contact_id=$2 AND
        status= 'active'
        """
            ),
            account,
            contact_id,
        )
        if (old and old["version"] != body.version) or (
            not old and body.version is not None
        ):
            raise HTTPException(409, "Tarefa alterada por outra pessoa; atualize")
        assigned_to = (
            body.assigned_to
            if "assigned_to" in body.model_fields_set
            else (old["assigned_to"] if old else user["id"])
        )
        if (
            assigned_to is not None
            and assigned_to != user["id"]
            and (not old or assigned_to != old["assigned_to"])
        ):
            try:
                async with await Chatwoot.for_account(conn, account) as cw:
                    members = await cw.request("GET", "/agents")
                if isinstance(members, dict):
                    members = members.get("payload", [])
                member = next((m for m in members if m["id"] == assigned_to), None)
                if member is None:
                    raise HTTPException(422, "Responsável não pertence à conta")
                await agent(
                    conn,
                    {
                        "account": account,
                        "id": assigned_to,
                        "name": member["name"],
                        "role": member.get("role", "agent"),
                    },
                )
            except (httpx.HTTPError, ValueError, KeyError, TypeError):
                raise HTTPException(
                    503, "Não foi possível validar o responsável"
                ) from None
        if old:
            await conn.execute(
                (
                    """
        UPDATE kb_tasks SET
        message=$3,due_date=$4,due_state=$5,assigned_to=$6,version=version+1 WHERE
        account_id=$1 AND id=$2
        """
                ),
                account,
                old["id"],
                body.descricao,
                body.vencimento,
                task_state(body.vencimento),
                assigned_to,
            )
        else:
            await conn.execute(
                (
                    """
        INSERT INTO
        kb_tasks(account_id,contact_id,message,due_date,created_by,due_state,assigned_to)
        VALUES($1,$2,$3,$4,$5,$6,$7)
        """
                ),
                account,
                contact_id,
                body.descricao,
                body.vencimento,
                user["id"],
                task_state(body.vencimento),
                assigned_to,
            )
        await record(
            conn,
            account,
            contact_id,
            user,
            "tarefa_editada" if old else "tarefa_criada",
            jsonable_encoder(dict(old)) if old else None,
            {**body.model_dump(mode="json"), "assigned_to": assigned_to},
        )
    return {"ok": True}


@router.post("/contacts/{contact_id}/task/close")
async def close_task(contact_id: int, body: Version, user=AUTH):
    account = user["account"]
    async with connection(user) as conn, conn.transaction():
        await agent(conn, user)
        await lock_contact(conn, account, contact_id)
        old = require(
            await conn.fetchrow(
                (
                    """
        SELECT * FROM kb_tasks WHERE account_id=$1 AND contact_id=$2 AND
        status= 'active'
        """
                ),
                account,
                contact_id,
            )
        )
        if old["version"] != body.version:
            raise HTTPException(409, "Tarefa alterada por outra pessoa; atualize")
        await conn.execute(
            (
                """
        UPDATE kb_tasks SET status= 'closed'
        ,closed_at=now(),closed_by=$3,version=version+1 WHERE account_id=$1
        AND id=$2
        """
            ),
            account,
            old["id"],
            user["id"],
        )
        await record(
            conn,
            account,
            contact_id,
            user,
            "tarefa_encerrada",
            jsonable_encoder(dict(old)),
        )
    return {"ok": True}


@router.get("/history")
async def history(
    contact_id: int | None = None,
    funnel_id: int | None = None,
    stage_id: int | None = None,
    actor_id: int | None = None,
    action: str | None = None,
    before: int = 9223372036854775807,
    user=AUTH,
):
    async with connection(user) as conn:
        rows = await conn.fetch(
            (
                """
        SELECT * FROM kb_visible_history WHERE account_id=$1 AND id<$2 AND
        ($3::integer IS NULL OR contact_id=$3) AND ($4::bigint IS NULL OR
        funnel_id=$4) AND ($5::bigint IS NULL OR stage_id=$5) AND ($6::integer
        IS NULL OR actor_id=$6) AND ($7::text IS NULL OR action=$7) ORDER BY
        id DESC LIMIT 50
        """
            ),
            user["account"],
            before,
            contact_id,
            funnel_id,
            stage_id,
            actor_id,
            action,
        )
    return jsonable_encoder([dict(r) for r in rows])


@router.get("/reports")
async def reports(
    funnel_id: int | None = None,
    days: int = Query(30, ge=1, le=365),
    user=AUTH,
):
    async with connection(user) as conn:
        stages = await conn.fetch(
            (
                """
        SELECT f.id AS funnel_id,f.name AS funnel,s.id AS stage_id, s.name AS
        stage,s.kind,count(c.id) AS quantity,coalesce(sum(c.value_cents),0) AS
        value_cents, avg(extract(epoch FROM now()-c.stage_entered_at))/86400
        AS current_dwell_days FROM kb_funnels f JOIN kb_stages s ON
        (s.account_id,s.funnel_id)=(f.account_id,f.id) LEFT JOIN kb_visible_cards c ON
        (c.account_id,c.stage_id)=(s.account_id,s.id) WHERE f.account_id=$1
        AND NOT f.archived AND NOT s.archived GROUP BY f.id,s.id ORDER BY
        f.position,s.position
        """
            ),
            user["account"],
        )
        agents = await conn.fetch(
            (
                """
        SELECT actor_id,actor_name,count(*) AS actions FROM kb_visible_history WHERE
        account_id=$1 AND actor_id IS NOT NULL GROUP BY actor_id,actor_name
        """
            ),
            user["account"],
        )
        dwell = await conn.fetch(
            (
                """
        SELECT funnel_id,(before_state->> 'stage_id' )::bigint AS stage_id,
        avg(extract(epoch FROM created_at-(before_state->> 'entered_at'
        )::timestamptz))/86400 AS days FROM kb_visible_history WHERE account_id=$1 AND
        action= 'cartao_movido' AND before_state->> 'stage_id'
        <>after_state->> 'stage_id' AND before_state ? 'entered_at' GROUP BY
        funnel_id,before_state->> 'stage_id'
        """
            ),
            user["account"],
        )
        timeline = await evolution(conn, user["account"], funnel_id, days)
    totals = {}
    for stage in stages:
        total = totals.setdefault(stage["funnel_id"], {"won": 0, "lost": 0})
        if stage["kind"] in total:
            total[stage["kind"]] += stage["quantity"]
    conversion = {
        fid: (t["won"] / (t["won"] + t["lost"]) if t["won"] + t["lost"] else None)
        for fid, t in totals.items()
    }
    return jsonable_encoder(
        {
            "stages": [dict(r) for r in stages],
            "agents": [dict(r) for r in agents],
            "dwell": [dict(r) for r in dwell],
            "conversion": conversion,
            "evolution": timeline,
        }
    )


@router.post("/sync/retry")
async def retry(user=AUTH):
    administrator(user)
    async with connection(user) as conn:
        await conn.execute(
            (
                """
        UPDATE kb_sync SET status= 'pending' ,next_attempt=now(),attempts=0
        WHERE account_id=$1 AND status<> 'synced'
        """
            ),
            user["account"],
        )
        await conn.execute(
            (
                """
        UPDATE kb_deliveries SET next_attempt=now() WHERE account_id=$1 AND
        status= 'failed'
        """
            ),
            user["account"],
        )
    return {"ok": True}


async def visible_revision(user):
    """Invalida apenas se a representação autorizada mudou, sem revelar IDs."""
    async with connection(user) as conn:
        return await conn.fetchval(
            """
            SELECT md5(jsonb_build_array(
              (SELECT jsonb_agg(to_jsonb(c) ORDER BY c.id) FROM kb_visible_cards c),
              (SELECT max(id) FROM kb_visible_history),
              (SELECT jsonb_agg(jsonb_build_array(contact_id,name,phone,email,
                thumbnail,labels) ORDER BY contact_id) FROM kb_contacts WHERE
        account_id=$1),
              (SELECT jsonb_agg(to_jsonb(t) ORDER BY t.id) FROM kb_tasks t
        WHERE account_id=$1),
              (SELECT jsonb_agg(to_jsonb(f) ORDER BY f.id) FROM kb_funnels f
        WHERE account_id=$1),
              (SELECT jsonb_agg(to_jsonb(s) ORDER BY s.id) FROM kb_stages s
        WHERE account_id=$1)
            )::text)
        """,
            user["account"],
        )


@router.get("/events")
async def events(request: Request, user=AUTH):
    async with connection(user):
        pass  # Negar a conta desativada antes dos cabeçalhos SSE.
    lease = hub.lease(user["account"])

    async def stream():
        current = user
        async with hub.subscribe(user["account"], lease=lease) as signal:
            try:
                revision = await visible_revision(user)
            except HTTPException:
                yield "event: expired\ndata: {}\n\n"
                return
            yield "event: ready\ndata: {}\n\n"
            checked = time.monotonic()
            while not await request.is_disconnected():
                deadline = min(
                    checked + min(settings.session_recheck_seconds, 30),
                    current.get("permission_deadline", checked + 60),
                )
                wait = max(0.01, min(10, deadline - time.monotonic()))
                with contextlib.suppress(TimeoutError):
                    await asyncio.wait_for(signal.wait(), timeout=wait)
                changed = signal.is_set()
                if changed:
                    await asyncio.sleep(0.1)
                signal.clear()
                if hub.connection is None:
                    yield "event: unavailable\ndata: {}\n\n"
                    return
                try:
                    if changed or time.monotonic() >= deadline:
                        current = await identity(request)
                        if (
                            current["account"] != user["account"]
                            or current["id"] != user["id"]
                        ):
                            raise HTTPException(403, "Sessão alterada")
                        checked = time.monotonic()
                    if changed or time.monotonic() >= deadline:
                        updated = await visible_revision(current)
                    else:
                        updated = revision
                except HTTPException as error:
                    event = "unavailable" if error.status_code == 503 else "expired"
                    yield f"event: {event}\ndata: {{}}\n\n"
                    return
                if updated != revision:
                    revision = updated
                    yield "event: change\ndata: {}\n\n"
                elif not changed:
                    yield ": keepalive\n\n"

    return EventResponse(
        stream(),
        lease=lease,
        media_type="text/event-stream",
        headers={"Cache-Control": "no-cache", "X-Accel-Buffering": "no"},
    )


@router.post("/webhooks/{account_id}/events")
async def webhook(account_id: int, request: Request):
    raw = await request.body()
    if len(raw) > 2_000_000:
        raise HTTPException(413, "Evento muito grande")
    timestamp = request.headers.get("x-chatwoot-timestamp", "")
    delivery = request.headers.get("x-chatwoot-delivery", "")
    if (
        len(timestamp) > 12
        or not timestamp.isdigit()
        or abs(time.time() - int(timestamp)) > settings.webhook_tolerance
        or not delivery
        or len(delivery) > 200
    ):
        raise HTTPException(401, "Assinatura inválida ou expirada")
    async with connection() as conn, conn.transaction():
        secret = await conn.fetchval(
            "SELECT webhook_cipher FROM kb_accounts WHERE account_id=$1 AND "
            "enabled FOR SHARE",
            account_id,
        )
        if not secret:
            raise HTTPException(401, "Assinatura inválida")
        expected = (
            "sha256="
            + hmac.new(
                decrypt(secret).encode(),
                timestamp.encode() + b"." + raw,
                hashlib.sha256,
            ).hexdigest()
        )
        if not hmac.compare_digest(
            expected.encode(), request.headers.get("x-chatwoot-signature", "").encode()
        ):
            raise HTTPException(401, "Assinatura inválida")
        try:
            payload = json.loads(raw)
            event = payload["event"]
            if payload.get("account", {}).get("id") != account_id:
                raise HTTPException(403, "Conta do evento não corresponde")
            contact = (
                payload.get("id")
                if event.startswith("contact_")
                else payload.get("meta", {}).get("sender", {}).get("id")
            )
        except (ValueError, KeyError, TypeError, AttributeError):
            raise HTTPException(400, "Evento inválido") from None
        await conn.execute(
            (
                """
        INSERT INTO
        kb_deliveries(account_id,delivery_id,event_type,contact_id,payload)
        VALUES($1,$2,$3,$4,$5) ON CONFLICT(account_id,delivery_id) DO NOTHING
        """
            ),
            account_id,
            delivery,
            event,
            contact,
            payload,
        )
    return {"received": True}
