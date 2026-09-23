import subprocess

import pytest

from app.config import settings
from app.database import connection
from scripts import import_legacy


async def test_legacy_copy_is_atomic_idempotent_and_preserves_source(
    db, monkeypatch, tmp_path
):
    async def noop():
        pass

    async def members(_self, _method, _path):
        return [{"id": 3, "name": "Ana", "email": "ana@example.test", "role": "agent"}]

    monkeypatch.setattr(import_legacy, "init_pool", noop)
    monkeypatch.setattr(import_legacy, "close_pool", noop)
    monkeypatch.setattr(import_legacy.Chatwoot, "request", members)
    async with connection() as conn:
        await conn.execute("""
            CREATE TABLE agentes(id integer, chatwoot_agent_id integer,
            email text); INSERT INTO agentes VALUES(1,3,'ana@example.test');
            CREATE TABLE tareas(id bigint,contact_id integer,mensaje text,
            fecha_vencimiento date,estado text,creado_por integer,cerrado_por integer,
            created_at timestamptz,cerrado_en timestamptz);
            INSERT INTO tareas VALUES(1,10,'Preservar tarefa','2026-09-23',
            'tarea_cerrada',1,1,now(),now());
            CREATE TABLE task_audit_log(id bigint,contact_id integer,
            actor_agent_id integer,
            actor_name text,action text,previous_state jsonb,new_state jsonb,
            created_at timestamptz);
            INSERT INTO task_audit_log VALUES(1,10,1,'Ana','closed','{}','{}',now());
            """)
    backup = tmp_path / "legacy.dump"
    subprocess.run(
        ["pg_dump", "-Fc", "-d", settings.database_url, "-f", str(backup)], check=True
    )
    try:
        await import_legacy.migrate(1, backup, False)
        async with connection() as conn:
            assert await conn.fetchval("SELECT count(*) FROM kb_tasks") == 0
        await import_legacy.migrate(1, backup, True)
        await import_legacy.migrate(1, backup, True)
        async with connection() as conn:
            assert await conn.fetchval("SELECT count(*) FROM tareas") == 1
            assert await conn.fetchval("SELECT count(*) FROM task_audit_log") == 1
            assert await conn.fetchval("SELECT count(*) FROM kb_tasks") == 1
            assert await conn.fetchval("SELECT status FROM kb_tasks") == "closed"
            assert await conn.fetchval("SELECT closed_by FROM kb_tasks") == 3
            assert await conn.fetchval("SELECT count(*) FROM kb_legacy_imports") == 2
            assert (
                await conn.fetchval(
                    "SELECT count(*) FROM kb_history WHERE action='legado:closed'"
                )
                == 1
            )
        with pytest.raises(ValueError, match="outra conta"):
            await import_legacy.migrate(2, backup, True)
        async with connection() as conn:
            await conn.execute(
                """INSERT INTO tareas
                VALUES(2,NULL,'Ambígua','2026-09-23',
                'tarea_activa',1,NULL,now(),NULL)"""
            )
        with pytest.raises(ValueError, match="sem contato"):
            await import_legacy.migrate(1, backup, True)
        async with connection() as conn:
            assert await conn.fetchval("SELECT count(*) FROM kb_tasks") == 1
    finally:
        async with connection() as conn:
            await conn.execute("DROP TABLE tareas,agentes,task_audit_log")
