"""Migração única de espelhos legados locais; dry-run por padrão, sem dados em logs."""

import argparse
import asyncio
import json
from datetime import date

from app.config import settings
from app.database import close_pool, connection, init_pool, lock_contact, record
from app.services import SYSTEM, task_state

LEGACY = ("pipeline_01_etapas", "kanban_view_mensaje", "kanban_view_fecha_termino")


async def migrate(conn, account: int, apply: bool = False) -> list[dict]:
    """Migra apenas lacunas; divergência com estado local bloqueia aquele contato."""
    report = []
    contacts = await conn.fetch(
        """SELECT contact_id FROM kb_contacts WHERE account_id=$1
        AND remote_attributes ?| $2::text[] ORDER BY contact_id""",
        account,
        list(LEGACY),
    )
    for contact in contacts:
        cid = contact["contact_id"]
        async with conn.transaction():
            await lock_contact(conn, account, cid)
            attrs = await conn.fetchval(
                "SELECT remote_attributes FROM kb_contacts WHERE "
                "account_id=$1 AND contact_id=$2",
                account,
                cid,
            )
            stage = await conn.fetchrow(
                """SELECT s.id,s.funnel_id FROM kb_stages s JOIN kb_funnels f
                ON (f.account_id,f.id)=(s.account_id,s.funnel_id)
                WHERE s.account_id=$1 AND f.is_primary AND NOT f.archived
                AND NOT s.archived AND s.name=$2""",
                account,
                attrs.get(LEGACY[0]),
            )
            card = await conn.fetchrow(
                """SELECT c.stage_id FROM kb_cards c JOIN kb_funnels f
                ON (f.account_id,f.id)=(c.account_id,c.funnel_id)
                WHERE c.account_id=$1 AND c.contact_id=$2 AND f.is_primary""",
                account,
                cid,
            )
            task = await conn.fetchrow(
                """SELECT message,due_date FROM kb_tasks WHERE account_id=$1
                AND contact_id=$2 AND status='active'""",
                account,
                cid,
            )
            message, raw_due = attrs.get(LEGACY[1]), attrs.get(LEGACY[2])
            try:
                due = date.fromisoformat(str(raw_due)) if raw_due else None
                invalid = bool(message) != bool(due)
            except ValueError:
                due, invalid = None, True
            conflict = (
                invalid
                or (attrs.get(LEGACY[0]) and not stage)
                or (card and stage and card["stage_id"] != stage["id"])
                or (
                    task
                    and message
                    and (task["message"], task["due_date"]) != (message, due)
                )
            )
            status = (
                "bloqueado"
                if conflict
                else "criar"
                if (stage and not card) or (message and not task)
                else "reutilizar"
            )
            report.append(
                {
                    "account_id": account,
                    "contact_id": cid,
                    "status": status,
                    "aplicado": apply and not conflict,
                }
            )
            if not apply or conflict:
                continue
            if stage and not card:
                await conn.execute(
                    """INSERT INTO kb_cards(account_id,contact_id,funnel_id,stage_id,
                    conversation_id,conversation_inbox_id)
                    SELECT account_id,contact_id,$3,$4,conversation_id,inbox_id
                    FROM kb_contacts WHERE account_id=$1 AND contact_id=$2""",
                    account,
                    cid,
                    stage["funnel_id"],
                    stage["id"],
                )
            if message and not task:
                await conn.execute(
                    """INSERT INTO
            kb_tasks(account_id,contact_id,message,due_date,due_state)
                    VALUES($1,$2,$3,$4,$5)""",
                    account,
                    cid,
                    message,
                    due,
                    task_state(due),
                )
            await conn.execute(
                """UPDATE kb_contacts SET remote_attributes=remote_attributes-$3::text[]
                WHERE account_id=$1 AND contact_id=$2""",
                account,
                cid,
                list(LEGACY),
            )
            await record(conn, account, cid, SYSTEM, "migracao_desenvolvimento")
    return report


async def main(account: int, apply: bool) -> None:
    if settings.env != "development":
        raise SystemExit("Permitido somente com ENV=development e backup prévio")
    await init_pool()
    try:
        async with connection() as conn:
            print(json.dumps(await migrate(conn, account, apply), ensure_ascii=False))
    finally:
        await close_pool()


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--account", required=True, type=int)
    mode = parser.add_mutually_exclusive_group()
    mode.add_argument(
        "--apply", action="store_true", help="Executa após revisar dry-run"
    )
    mode.add_argument("--dry-run", action="store_true", help="Padrão: só relatório")
    args = parser.parse_args()
    asyncio.run(main(args.account, args.apply))
