"""Reparo de dados de métricas de uma conta, com simulação.

Uso, dentro do container do Kanban (acesso ao banco = operador da instalação):

    python -m app.maintenance --account 8 --dry-run \\
        --backfill-created 2026-09-25 --won-at 12=2026-09-23 --renumber-stages

Sem ``--dry-run`` as alterações são gravadas numa transação por negociação e
registradas em ``kb_history`` como ``manutencao_metricas``. Rodar de novo não
altera o que já está corrigido.
"""

import argparse
import asyncio
from datetime import UTC, date, datetime, time

import httpx

from app.chatwoot_client import Chatwoot
from app.database import close_pool, connection, init_pool, lock_contact, record
from app.routers.workspace import BRAZIL

MAINTENANCE = {"id": None, "name": "Manutenção"}
ACTION = "manutencao_metricas"


def noon(day: date) -> datetime:
    """Meio-dia de Brasília: o dia informado não muda em nenhum fuso do Brasil."""
    return datetime.combine(day, time(12), BRAZIL)


def won_argument(value: str) -> tuple[int, date]:
    card, _, day = value.partition("=")
    try:
        return int(card), date.fromisoformat(day)
    except ValueError:
        raise argparse.ArgumentTypeError("Use CARTAO=AAAA-MM-DD") from None


async def first_contact(cw: Chatwoot, contact_id: int) -> datetime | None:
    """Abertura da conversa mais antiga do contato, ou o cadastro na falta dela."""
    conversations = await cw.request("GET", f"/contacts/{contact_id}/conversations")
    opened = [
        c["created_at"]
        for c in conversations.get("payload", [])
        if isinstance(c.get("created_at"), (int, float)) and c["created_at"] > 0
    ]
    if not opened:
        data = await cw.request("GET", f"/contacts/{contact_id}")
        created = data.get("payload", data).get("created_at")
        opened = [created] if isinstance(created, (int, float)) else []
    return datetime.fromtimestamp(min(opened), UTC) if opened else None


async def backfill_created(conn, account: int, day: date) -> int:
    """Leva a criação dos cartões criados em ``day`` para o primeiro contato.

    Só o primeiro cartão de cada contato é alterado: negociações abertas depois
    para o mesmo contato continuam com a própria data.
    """
    cards = await conn.fetch(
        """SELECT c.* FROM kb_cards c WHERE c.account_id=$1
        AND (c.created_at AT TIME ZONE 'America/Sao_Paulo')::date=$2
        AND c.id=(SELECT min(o.id) FROM kb_cards o WHERE o.account_id=c.account_id
        AND o.contact_id=c.contact_id) ORDER BY c.id""",
        account,
        day,
    )
    changed = 0
    async with await Chatwoot.for_account(conn, account) as cw:
        for card in cards:
            try:
                first = await first_contact(cw, card["contact_id"])
            except httpx.HTTPStatusError as exc:
                print(
                    f"Cartão {card['id']}: contato indisponível "
                    f"({exc.response.status_code})"
                )
                continue
            if not first or first >= card["created_at"]:
                continue
            changed += 1
            moved = await conn.fetchval(
                """SELECT EXISTS(SELECT 1 FROM kb_card_events WHERE account_id=$1
                AND card_id=$2 AND event_type='moved')""",
                account,
                card["id"],
            )
            print(
                f"Cartão {card['id']}: criado {card['created_at']:%d/%m/%Y %H:%M} -> "
                f"{first.astimezone(BRAZIL):%d/%m/%Y %H:%M}"
            )
            async with conn.transaction():
                await lock_contact(conn, account, card["contact_id"])
                await conn.execute(
                    """UPDATE kb_contacts SET first_seen_at=least(first_seen_at,$3)
                    WHERE account_id=$1 AND contact_id=$2""",
                    account,
                    card["contact_id"],
                    first,
                )
                # Sem movimento, a entrada na etapa atual também é a criação.
                await conn.execute(
                    """UPDATE kb_cards SET created_at=$3,stage_entered_at=CASE WHEN $4
                    THEN stage_entered_at ELSE $3 END WHERE account_id=$1 AND id=$2""",
                    account,
                    card["id"],
                    first,
                    moved,
                )
                await conn.execute(
                    """UPDATE kb_card_events SET created_at=$3,entered_at=$3
                    WHERE account_id=$1 AND card_id=$2 AND event_type='created'""",
                    account,
                    card["id"],
                    first,
                )
                if not moved:
                    await conn.execute(
                        """UPDATE kb_card_events SET entered_at=$3 WHERE account_id=$1
                        AND card_id=$2 AND event_type IN ('updated','baseline')""",
                        account,
                        card["id"],
                        first,
                    )
                await record(
                    conn,
                    account,
                    card["contact_id"],
                    MAINTENANCE,
                    ACTION,
                    {"created_at": card["created_at"].isoformat()},
                    {"card_id": card["id"], "created_at": first.isoformat()},
                    card["funnel_id"],
                    card["stage_id"],
                    sync=False,
                )
    return changed


async def set_won_at(conn, account: int, card_id: int, day: date) -> bool:
    """Registra a data real do ganho na última entrada da etapa de ganho."""
    when = noon(day)
    card = await conn.fetchrow(
        """SELECT c.*,s.kind FROM kb_cards c JOIN kb_stages s ON
        (s.account_id,s.id)=(c.account_id,c.stage_id)
        WHERE c.account_id=$1 AND c.id=$2""",
        account,
        card_id,
    )
    if not card or card["kind"] != "won":
        raise SystemExit(f"Cartão {card_id}: não está numa etapa de ganho")
    entry = await conn.fetchrow(
        """SELECT * FROM kb_card_events WHERE account_id=$1 AND card_id=$2
        AND event_type IN ('created','moved') ORDER BY created_at DESC,id DESC
        LIMIT 1""",
        account,
        card_id,
    )
    previous = await conn.fetchval(
        """SELECT max(created_at) FROM kb_card_events WHERE account_id=$1
        AND card_id=$2 AND event_type IN ('created','moved') AND id<>$3
        AND (created_at,id)<($4,$3)""",
        account,
        card_id,
        entry["id"],
        entry["created_at"],
    )
    if when > datetime.now(UTC):
        raise SystemExit(f"Cartão {card_id}: data no futuro")
    if when < card["created_at"] or (previous and when < previous):
        raise SystemExit(
            f"Cartão {card_id}: {day:%d/%m/%Y} é anterior à criação ou ao "
            "movimento anterior; corrija a criação antes (--backfill-created)"
        )
    if entry["created_at"] == when and card["won_at"] == when:
        return False
    print(
        f"Cartão {card_id}: ganho {entry['created_at']:%d/%m/%Y %H:%M} -> "
        f"{when:%d/%m/%Y %H:%M}"
    )
    async with conn.transaction():
        await lock_contact(conn, account, card["contact_id"])
        await conn.execute(
            "UPDATE kb_card_events SET created_at=$3,entered_at=$3 "
            "WHERE account_id=$1 AND id=$2",
            account,
            entry["id"],
            when,
        )
        await conn.execute(
            """UPDATE kb_card_events SET entered_at=$3 WHERE account_id=$1
            AND card_id=$2 AND event_type IN ('updated','baseline') AND
            (created_at,id)>($4,$5)""",
            account,
            card_id,
            when,
            entry["created_at"],
            entry["id"],
        )
        await conn.execute(
            "UPDATE kb_cards SET won_at=$3,stage_entered_at=$3 "
            "WHERE account_id=$1 AND id=$2",
            account,
            card_id,
            when,
        )
        await record(
            conn,
            account,
            card["contact_id"],
            MAINTENANCE,
            ACTION,
            {"won_at": entry["created_at"].isoformat()},
            {"card_id": card_id, "won_at": when.isoformat()},
            card["funnel_id"],
            card["stage_id"],
            sync=False,
        )
    return True


async def renumber_stages(conn, account: int) -> int:
    """Renumera funis com posições repetidas, na ordem atual (posição, id)."""
    funnels = await conn.fetch(
        """SELECT DISTINCT funnel_id FROM kb_stages WHERE account_id=$1 AND NOT
        archived GROUP BY funnel_id,position HAVING count(*)>1""",
        account,
    )
    for funnel in funnels:
        stages = await conn.fetch(
            """SELECT id,name,position FROM kb_stages WHERE account_id=$1 AND
            funnel_id=$2 AND NOT archived ORDER BY position,id""",
            account,
            funnel["funnel_id"],
        )
        print(
            f"Funil {funnel['funnel_id']}: "
            + ", ".join(
                f"{s['name']} {s['position']}->{(i + 1) * 1024}"
                for i, s in enumerate(stages)
            )
        )
        async with conn.transaction():
            await conn.execute(
                "SELECT id FROM kb_funnels WHERE account_id=$1 AND id=$2 FOR UPDATE",
                account,
                funnel["funnel_id"],
            )
            for i, stage in enumerate(stages):
                await conn.execute(
                    "UPDATE kb_stages SET position=$3 WHERE account_id=$1 AND id=$2",
                    account,
                    stage["id"],
                    (i + 1) * 1024,
                )
            await record(
                conn,
                account,
                None,
                MAINTENANCE,
                ACTION,
                {"positions": {str(s["id"]): str(s["position"]) for s in stages}},
                {
                    "positions": {
                        str(s["id"]): (i + 1) * 1024 for i, s in enumerate(stages)
                    }
                },
                funnel["funnel_id"],
                sync=False,
            )
    return len(funnels)


async def main(args: argparse.Namespace) -> None:
    await init_pool()
    try:
        async with connection() as conn:
            if not await conn.fetchval(
                "SELECT 1 FROM kb_accounts WHERE account_id=$1", args.account
            ):
                raise SystemExit(f"Conta {args.account} não ativada no Kanban")
            label = "Simulação" if args.dry_run else "Aplicado"
            # A simulação grava de verdade e desfaz no fim: cada etapa enxerga as
            # anteriores, como na execução real.
            rehearsal = conn.transaction() if args.dry_run else None
            if rehearsal:
                await rehearsal.start()
            try:
                if args.renumber_stages:
                    total = await renumber_stages(conn, args.account)
                    print(f"{label}: {total} funis com posições repetidas")
                if args.backfill_created:
                    total = await backfill_created(
                        conn, args.account, args.backfill_created
                    )
                    print(f"{label}: {total} cartões com a criação retroagida")
                for card_id, day in args.won_at:
                    await set_won_at(conn, args.account, card_id, day)
            finally:
                if rehearsal:
                    await rehearsal.rollback()
    finally:
        await close_pool()


def parser() -> argparse.ArgumentParser:
    cli = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    cli.add_argument("--account", type=int, required=True)
    cli.add_argument("--dry-run", action="store_true", help="mostra sem gravar")
    cli.add_argument(
        "--backfill-created",
        type=date.fromisoformat,
        metavar="AAAA-MM-DD",
        help="dia da importação cujos cartões voltam para o primeiro contato",
    )
    cli.add_argument(
        "--won-at",
        type=won_argument,
        action="append",
        default=[],
        metavar="CARTAO=AAAA-MM-DD",
        help="data real de um ganho; repita para vários cartões",
    )
    cli.add_argument(
        "--renumber-stages",
        action="store_true",
        help="renumera etapas com posições repetidas",
    )
    return cli


if __name__ == "__main__":
    asyncio.run(main(parser().parse_args()))
