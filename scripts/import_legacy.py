"""Importação explícita e transacional; mantém tabelas originais para recuperação."""

import argparse
import asyncio
import subprocess
from pathlib import Path

from app.chatwoot_client import Chatwoot
from app.database import close_pool, connection, init_pool, record
from app.services import SYSTEM, task_state


async def migrate(account, backup, apply):
    if not backup.is_file() or backup.stat().st_size < 100:
        raise ValueError("Informe um backup pg_dump -Fc válido do banco de origem")
    listing = subprocess.run(
        ["pg_restore", "--list", str(backup)],
        check=True,
        capture_output=True,
        text=True,
    ).stdout
    await init_pool()
    try:
        async with connection() as conn, conn.transaction():
            await conn.execute("SELECT pg_advisory_xact_lock(900001,$1)", account)
            if not await conn.fetchval("SELECT to_regclass('public.tareas')"):
                raise ValueError("Tabelas legadas ausentes neste banco")
            database = await conn.fetchval("SELECT current_database()")
            if f"dbname: {database}\n" not in listing:
                raise ValueError("O backup não corresponde ao banco de origem")
            await conn.execute("LOCK TABLE agentes,tareas IN SHARE MODE")
            if await conn.fetchval("SELECT to_regclass('public.task_audit_log')"):
                await conn.execute("LOCK TABLE task_audit_log IN SHARE MODE")
            rows = await conn.fetch("SELECT * FROM tareas ORDER BY id")
            agents = await conn.fetch("SELECT * FROM agentes")
            async with await Chatwoot.for_account(conn, account) as cw:
                members = await cw.request("GET", "/agents")
            members = {m["id"]: m for m in members}
            mapping = {}
            for agent in agents:
                uid = agent["chatwoot_agent_id"]
                if (
                    uid not in members
                    or members[uid]["email"].lower() != agent["email"].lower()
                ):
                    raise ValueError(
                        f"Agente legado {agent['id']} não tem associação inequívoca"
                    )
                mapping[agent["id"]] = uid
            for row in rows:
                contact = row["contact_id"]
                if not contact or not await conn.fetchval(
                    """SELECT 1 FROM kb_contacts
                        WHERE account_id=$1 AND contact_id=$2""",
                    account,
                    contact,
                ):
                    raise ValueError(
                        f"Tarefa {row['id']} sem contato importado da conta informada"
                    )
                if not row["fecha_vencimiento"]:
                    raise ValueError(f"Tarefa {row['id']} sem vencimento válido")
                old = await conn.fetchrow(
                    """
        SELECT account_id FROM kb_legacy_imports WHERE source_table= 'tareas'
        AND source_id=$1
        """,
                    row["id"],
                )
                if old and old["account_id"] != account:
                    raise ValueError("Origem já vinculada a outra conta")
                if old:
                    continue
                closed = row["estado"] in ("tarea_cerrada", "cerrada", "closed")
                if not closed and await conn.fetchval(
                    """
        SELECT 1 FROM kb_tasks WHERE account_id=$1 AND contact_id=$2 AND
        status= 'active'
        """,
                    account,
                    contact,
                ):
                    raise ValueError(
                        f"Contato {contact} já tem tarefa ativa; resolva a ambiguidade"
                    )
            if not apply:
                print(
                    f"Validação concluída: {len(rows)} tarefas; "
                    "nenhuma alteração aplicada."
                )
                return
            for legacy in agents:
                member = members[mapping[legacy["id"]]]
                await conn.execute(
                    """
        INSERT INTO kb_agents(account_id,user_id,name,role)
        VALUES($1,$2,$3,$4) ON CONFLICT(account_id,user_id) DO NOTHING
        """,
                    account,
                    member["id"],
                    member["name"],
                    member["role"],
                )
            for row in rows:
                if await conn.fetchval(
                    """
        SELECT 1 FROM kb_legacy_imports WHERE source_table= 'tareas' AND
        source_id=$1
        """,
                    row["id"],
                ):
                    continue
                closed = row["estado"] in ("tarea_cerrada", "cerrada", "closed")
                task = await conn.fetchval(
                    """
        INSERT INTO kb_tasks(account_id,contact_id,
        message,due_date,status,created_by,closed_by,created_at,closed_at,due_state)
        VALUES($1,$2,$3,$4,$5,$6,$7,$8,$9,$10) RETURNING id
        """,
                    account,
                    row["contact_id"],
                    row["mensaje"],
                    row["fecha_vencimiento"],
                    "closed" if closed else "active",
                    mapping.get(row["creado_por"]),
                    mapping.get(row["cerrado_por"]),
                    row["created_at"],
                    row["cerrado_en"],
                    task_state(row["fecha_vencimiento"]),
                )
                await conn.execute(
                    """
        INSERT INTO
        kb_legacy_imports(source_table,source_id,account_id,target_id) VALUES(
        'tareas' ,$1,$2,$3)
        """,
                    row["id"],
                    account,
                    task,
                )
                await record(
                    conn,
                    account,
                    row["contact_id"],
                    SYSTEM,
                    "tarefa_legada_importada",
                    after={"task_id": task},
                )
            if await conn.fetchval("SELECT to_regclass('public.task_audit_log')"):
                audits = await conn.fetch("SELECT * FROM task_audit_log ORDER BY id")
                for row in audits:
                    if row["actor_agent_id"] not in mapping:
                        raise ValueError("Autor do histórico sem associação inequívoca")
                    if row["contact_id"] and not await conn.fetchval(
                        """SELECT 1 FROM kb_contacts
                        WHERE account_id=$1 AND contact_id=$2""",
                        account,
                        row["contact_id"],
                    ):
                        raise ValueError(
                            "Histórico com associação ambígua; importação revertida"
                        )
                    old = await conn.fetchrow(
                        """
        SELECT * FROM kb_legacy_imports WHERE source_table= 'task_audit_log'
        AND source_id=$1
        """,
                        row["id"],
                    )
                    if old:
                        if old["account_id"] != account:
                            raise ValueError("Histórico já associado a outra conta")
                        continue
                    target = await conn.fetchval(
                        """
        INSERT INTO kb_history(account_id,
        contact_id,actor_id,actor_name,action,before_state,after_state,created_at)
        VALUES($1,$2,$3,$4,$5,$6,$7,$8) RETURNING id
        """,
                        account,
                        row["contact_id"],
                        mapping.get(row["actor_agent_id"]),
                        row["actor_name"],
                        "legado:" + row["action"],
                        row["previous_state"],
                        row["new_state"],
                        row["created_at"],
                    )
                    await conn.execute(
                        """
        INSERT INTO
        kb_legacy_imports(source_table,source_id,account_id,target_id) VALUES(
        'task_audit_log' ,$1,$2,$3)
        """,
                        row["id"],
                        account,
                        target,
                    )
            print("Importação concluída. Tabelas originais preservadas.")
    finally:
        await close_pool()


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("--account", type=int, required=True)
    parser.add_argument("--backup", type=Path, required=True)
    parser.add_argument("--apply", action="store_true")
    args = parser.parse_args()
    asyncio.run(migrate(args.account, args.backup, args.apply))
