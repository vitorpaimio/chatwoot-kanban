"""Provas de preservação e rollback da migração de negociações."""

from importlib import import_module

import asyncpg
import pytest

from app.database import connection, record


async def test_multiple_deals_migration_preserves_data_and_blocks_loss(db, monkeypatch):
    migration = import_module("migrations.versions.007_multiple_deals")
    statements = []
    monkeypatch.setattr(migration.op, "execute", statements.append)
    async with connection() as conn, conn.transaction():
        view_definition = await conn.fetchval(
            "SELECT pg_get_viewdef('kb_visible_cards'::regclass,true)"
        )
        card = await conn.fetchrow("SELECT * FROM kb_cards WHERE account_id=1")
        await record(
            conn,
            1,
            10,
            {"id": 3, "name": "Admin"},
            "cartao_movido",
            after={"stage_id": card["stage_id"]},
            funnel=card["funnel_id"],
            sync=False,
        )
        before = await conn.fetch("SELECT * FROM kb_cards ORDER BY id")
        migration.downgrade()
        for sql in statements:
            await conn.execute(sql)
        statements.clear()
        migration.upgrade()
        for sql in statements:
            await conn.execute(sql)
        assert await conn.fetch("SELECT * FROM kb_cards ORDER BY id") == before
        assert await conn.fetchval(
            "SELECT after_state->>'card_id' FROM kb_history WHERE account_id=1"
        ) == str(card["id"])
        await conn.execute(
            """INSERT INTO kb_cards
            (account_id,contact_id,funnel_id,stage_id)
            VALUES(1,10,$1,$2)""",
            card["funnel_id"],
            card["stage_id"],
        )
        statements.clear()
        migration.downgrade()
        with pytest.raises(asyncpg.UniqueViolationError):
            async with conn.transaction():
                for sql in statements:
                    await conn.execute(sql)
        assert (
            await conn.fetchval("SELECT count(*) FROM kb_cards WHERE account_id=1") == 2
        )

        await conn.execute(
            "CREATE OR REPLACE VIEW kb_visible_cards AS " + view_definition
        )
