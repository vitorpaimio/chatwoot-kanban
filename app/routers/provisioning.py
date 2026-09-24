"""Configuração administrativa, manifesto e importação explícita por conta."""

from asyncpg import Connection
from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel, ConfigDict, Field

from app.chatwoot_client import Chatwoot
from app.database import connection, notify, require_enabled
from app.provisioning.attributes import CATALOG, attribute_plan
from app.security import administrator, identity

router = APIRouter(prefix="/kanban")
AUTH = Depends(identity)


async def configuration_lock(conn: Connection, account: int) -> None:
    """Evita disputar configuração com uma unidade remota em andamento."""
    if not await conn.fetchval("SELECT pg_try_advisory_xact_lock(900000,$1)", account):
        raise HTTPException(409, "Conta em processamento; tente novamente em instantes")


class Mappings(BaseModel):
    model_config = ConfigDict(extra="forbid")
    origem: str | None = Field(default=None, pattern=r"^[a-zA-Z][a-zA-Z0-9_]{0,99}$")
    campanha: str | None = Field(default=None, pattern=r"^[a-zA-Z][a-zA-Z0-9_]{0,99}$")
    temperatura: str | None = Field(
        default=None, pattern=r"^[a-zA-Z][a-zA-Z0-9_]{0,99}$"
    )


class Configuration(BaseModel):
    model_config = ConfigDict(extra="forbid")
    mappings: Mappings
    processing_limit: int = Field(default=10, ge=1, le=100)


@router.get("/provisioning")
async def status(user=AUTH):
    administrator(user)
    async with connection() as conn:
        row = await conn.fetchrow(
            """SELECT attribute_mappings,processing_limit,provisioning_warnings,
            activation_status,activation_error,import_status,import_mode,import_page,
            imported_count,import_estimate,import_error,reconcile_error
            FROM kb_accounts WHERE account_id=$1""",
            user["account"],
        )
        if not row:
            raise HTTPException(404, "Conta não provisionada")
        resources = await conn.fetch(
            """SELECT resource_type,resource_key,remote_id,ownership,definition
            FROM kb_resources WHERE account_id=$1 ORDER BY
            resource_type,resource_key""",
            user["account"],
        )
        return {**dict(row), "resources": [dict(r) for r in resources]}


@router.put("/provisioning")
async def configure(body: Configuration, user=AUTH):
    administrator(user)
    mappings = body.mappings.model_dump()
    keys = [v for v in mappings.values() if v]
    if len(set(keys)) != len(keys) or set(keys) & {
        a.key for a in CATALOG if a.required
    }:
        raise HTTPException(
            422, "Cada dimensão exige uma chave própria, fora dos espelhos obrigatórios"
        )
    async with connection() as conn, conn.transaction():
        await configuration_lock(conn, user["account"])
        row = await conn.fetchrow(
            "SELECT * FROM kb_accounts WHERE account_id=$1 FOR UPDATE", user["account"]
        )
        if not row:
            raise HTTPException(404, "Conta não provisionada")
        await conn.execute(
            """UPDATE kb_accounts SET attribute_mappings=$2,processing_limit=$3,
            activation_status='pending',activation_error=NULL,activation_next_attempt=now(),
            provisioning_warnings='[]',
            activation_attempts=0,reconcile_cursor=0,reconcile_next_attempt=now()
            WHERE account_id=$1""",
            user["account"],
            mappings,
            body.processing_limit,
        )
        await conn.execute(
            "DELETE FROM kb_metrics_cache WHERE account_id=$1", user["account"]
        )
        await notify(conn, user["account"])
    return {"status": "pending"}


@router.get("/provisioning/plan")
async def plan(user=AUTH):
    administrator(user)
    async with connection() as conn:
        mappings = await conn.fetchval(
            "SELECT attribute_mappings FROM kb_accounts WHERE account_id=$1",
            user["account"],
        )
        if mappings is None:
            raise HTTPException(404, "Conta não provisionada")
        async with await Chatwoot.for_account(conn, user["account"]) as cw:
            definitions = await cw.request("GET", "/custom_attribute_definitions")
        return attribute_plan(definitions, mappings)


@router.post("/provisioning/retry")
async def retry(user=AUTH):
    administrator(user)
    async with connection() as conn, conn.transaction():
        await configuration_lock(conn, user["account"])
        await require_enabled(conn, user["account"], ready=False)
        await conn.execute(
            """UPDATE kb_accounts SET activation_status='pending',activation_error=NULL,
            activation_next_attempt=now(),activation_attempts=0 WHERE account_id=$1""",
            user["account"],
        )
    return {"status": "pending"}


@router.get("/import/estimate")
async def estimate(user=AUTH):
    administrator(user)
    async with connection(user) as conn:
        async with await Chatwoot.for_account(conn, user["account"]) as cw:
            response = await cw.request("GET", "/contacts", params={"page": 1})
        count = response.get("meta", {}).get("count")
        if not isinstance(count, int) or count < 0:
            raise HTTPException(502, "Chatwoot não forneceu a estimativa de contatos")
    async with connection() as conn:
        await conn.execute(
            "UPDATE kb_accounts SET import_estimate=$2 WHERE account_id=$1",
            user["account"],
            count,
        )
    return {"contacts": count, "default_mode": "metadata"}


class ImportRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")
    mode: str = Field(default="metadata", pattern="^(metadata|cards)$")
    funnel_id: int | None = None
    stage_id: int | None = None
    resume: bool = False


@router.post("/import")
async def start_import(body: ImportRequest | None = None, user=AUTH):
    administrator(user)
    body = body or ImportRequest()
    async with connection() as conn, conn.transaction():
        await configuration_lock(conn, user["account"])
        await require_enabled(conn, user["account"])
        row = await conn.fetchrow(
            "SELECT * FROM kb_accounts WHERE account_id=$1 FOR UPDATE", user["account"]
        )
        if body.resume:
            if row["import_status"] not in ("failed", "running", "pending"):
                raise HTTPException(409, "Não há importação pendente para retomar")
        else:
            if row["import_status"] in ("running", "pending", "failed"):
                raise HTTPException(
                    409, "Retome a importação existente antes de iniciar outra"
                )
            if row["import_estimate"] is None:
                raise HTTPException(409, "Consulte a estimativa antes de importar")
            if body.mode == "cards":
                stage = await conn.fetchval(
                    """SELECT s.id FROM kb_stages s JOIN kb_funnels f
                    ON (s.account_id,s.funnel_id)=(f.account_id,f.id)
                    WHERE s.account_id=$1 AND s.funnel_id=$2 AND s.id=$3
                    AND NOT s.archived AND NOT f.archived AND s.kind='open'""",
                    user["account"],
                    body.funnel_id,
                    body.stage_id,
                )
                if not stage:
                    raise HTTPException(
                        422, "Escolha uma etapa aberta e um funil ativo desta conta"
                    )
            await conn.execute(
                "DELETE FROM kb_import_seen WHERE account_id=$1", user["account"]
            )
            await conn.execute(
                """UPDATE kb_accounts SET
                   import_mode=$2,import_page=1,import_pending='[]',
                imported_count=0,import_actor=$3,import_funnel_id=$4,import_stage_id=$5
                WHERE account_id=$1""",
                user["account"],
                body.mode,
                {"id": user["id"], "name": user["name"]},
                body.funnel_id,
                body.stage_id,
            )
        await conn.execute(
            """UPDATE kb_accounts SET import_status='pending',import_requested=true,
            import_next_attempt=now(),import_error=NULL,import_attempts=0 WHERE
            account_id=$1""",
            user["account"],
        )
    return {"status": "pending"}
