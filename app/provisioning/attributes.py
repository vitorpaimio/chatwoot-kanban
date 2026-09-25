"""Catálogo e validação das definições de atributos do Chatwoot."""

from __future__ import annotations

from collections.abc import Awaitable, Callable
from dataclasses import dataclass
from typing import TYPE_CHECKING

from asyncpg import Connection

if TYPE_CHECKING:
    from app.chatwoot_client import Chatwoot


@dataclass(frozen=True)
class Attribute:
    """Contrato de um atributo de contato usado pelo Kanban."""

    key: str
    name: str
    description: str
    kind: str = "text"
    required: bool = True
    values: tuple[str, ...] = ()
    model: str = "contact_attribute"
    dynamic: bool = False

    def payload(self) -> dict:
        """Produz os parâmetros aceitos pela API de definições."""
        return {
            "attribute_key": self.key,
            "attribute_display_name": self.name,
            "attribute_description": self.description,
            "attribute_model": 1,
            "attribute_display_type": {"text": 0, "date": 5, "list": 6}[self.kind],
            "attribute_values": list(self.values),
        }


CATALOG = (
    # As opções acompanham os funis ativos; o worker converte versões em texto.
    Attribute(
        "kanban_etapa",
        "Funil / Etapa",
        "Etapa do Kanban. Escolher outra opção move o contato no quadro.",
        "list",
        values=tuple(
            f"Funil principal / {name}"
            for name in (
                "Novo",
                "Em atendimento",
                "Proposta enviada",
                "Ganho",
                "Perdido",
            )
        ),
        dynamic=True,
    ),
    Attribute("kanban_tarefa", "Tarefa do Kanban", "Espelho da tarefa local ativa."),
    Attribute(
        "kanban_tarefa_vencimento",
        "Vencimento da tarefa",
        "Espelho do vencimento da tarefa local ativa.",
        "date",
    ),
    Attribute("origem", "Origem", "Origem do contato.", required=False),
    Attribute("campanha", "Campanha", "Campanha do contato.", required=False),
    Attribute(
        "temperatura",
        "Temperatura",
        "Temperatura do contato.",
        "list",
        False,
        ("Frio", "Morno", "Quente"),
    ),
)


class AttributeConflictError(ValueError):
    """Conflito seguro para exibição, sem conteúdo remoto ou credenciais."""


async def ensure_required_attributes(cw: Chatwoot) -> None:
    """Valida todos os obrigatórios antes de criar definições ausentes.

    Args:
        cw: Cliente autenticado da conta a provisionar.

    Raises:
        AttributeConflictError: Uma chave obrigatória tem modelo ou tipo incompatível.
    """
    definitions = await cw.request("GET", "/custom_attribute_definitions")
    plan = attribute_plan(definitions, {})
    for item in plan:
        if item["status"] == "conflict":
            raise AttributeConflictError(item["diagnostic"])
    for item in plan:
        if item["status"] == "create":
            await cw.request(
                "POST", "/custom_attribute_definitions", json=item["payload"]
            )


async def remember_resource(
    conn: Connection, account: int, kind: str, key: str, resource: dict, created: bool
) -> None:
    """Registra propriedade confirmada, sem segredos do recurso remoto."""
    await conn.execute(
        """INSERT INTO kb_resources
        (account_id,resource_type,resource_key,remote_id,ownership,definition)
        VALUES($1,$2,$3,$4,$5,$6) ON CONFLICT(account_id,resource_type,resource_key)
        DO UPDATE SET remote_id=excluded.remote_id,definition=excluded.definition,
        ownership=CASE WHEN kb_resources.remote_id=excluded.remote_id
          THEN kb_resources.ownership ELSE excluded.ownership END,updated_at=now()""",
        account,
        kind,
        key,
        resource["id"],
        "created" if created else "preexisting",
        {
            k: v
            for k, v in resource.items()
            if k.startswith("attribute_") or k in ("url", "subscriptions")
        },
    )


def attribute_plan(definitions: list[dict], mappings: dict) -> list[dict]:
    """Calcula criação, reutilização ou conflito sem alterar a conta."""
    from dataclasses import replace

    result = []
    for original in CATALOG:
        key = original.key if original.required else mappings.get(original.key)
        if not key:
            result.append({"key": original.key, "status": "disabled"})
            continue
        attribute = replace(original, key=key)
        matches = [d for d in definitions if d["attribute_key"] == key]
        existing = next(
            (d for d in matches if d["attribute_model"] in (1, "contact_attribute")),
            None,
        )
        problem = None
        if existing is None and matches:
            problem = "modelo incompatível"
        elif existing and existing["attribute_display_type"] not in (
            attribute.kind,
            attribute.payload()["attribute_display_type"],
            *(("text", 0) if attribute.dynamic else ()),
        ):
            problem = "tipo incompatível"
        elif (
            existing
            and not attribute.dynamic
            and attribute.values
            and not set(attribute.values).issubset(
                set(existing.get("attribute_values") or [])
            )
        ):
            problem = "lista sem Frio, Morno e Quente"
        result.append(
            {
                "key": original.key,
                "mapped_key": key,
                "required": original.required,
                "status": "conflict" if problem else "reuse" if existing else "create",
                "diagnostic": f"{original.name}: {problem}" if problem else None,
                "existing": existing,
                "payload": attribute.payload(),
            }
        )
    return result


async def provision_attributes(
    conn: Connection,
    cw: Chatwoot,
    progress: Callable[[Connection], Awaitable[None]] | None = None,
) -> None:
    """Persiste cada recurso confirmado; conflitos opcionais desativam a dimensão."""
    from app.database import require_enabled

    async with conn.transaction():
        await require_enabled(conn, cw.account, ready=False)
        mappings = await conn.fetchval(
            "SELECT attribute_mappings FROM kb_accounts WHERE account_id=$1", cw.account
        )
        definitions = await cw.request("GET", "/custom_attribute_definitions")
        plan = attribute_plan(definitions, mappings)
        conflicts = [p for p in plan if p["status"] == "conflict" and p["required"]]
        if conflicts:
            raise AttributeConflictError("; ".join(p["diagnostic"] for p in conflicts))
        warnings = await conn.fetchval(
            "SELECT provisioning_warnings FROM kb_accounts WHERE account_id=$1",
            cw.account,
        )
        for item in plan:
            if item["status"] == "conflict":
                mappings[item["key"]] = None
                warnings.append(
                    item["diagnostic"]
                    + "; recurso desativado, configure outro mapeamento"
                )
        await conn.execute(
            """UPDATE kb_accounts SET attribute_mappings=$2,provisioning_warnings=$3
            WHERE account_id=$1""",
            cw.account,
            mappings,
            warnings,
        )
    for item in plan:
        if item["status"] not in ("create", "reuse"):
            continue
        async with conn.transaction():
            await require_enabled(conn, cw.account, ready=False)
            resource = item["existing"]
            created = resource is None
            if created:
                resource = await cw.request(
                    "POST", "/custom_attribute_definitions", json=item["payload"]
                )
            await remember_resource(
                conn,
                cw.account,
                "attribute",
                "contact:" + item["mapped_key"],
                resource,
                created,
            )
        if progress:
            await progress(conn)
