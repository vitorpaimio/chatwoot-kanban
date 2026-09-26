"""Unidades retomáveis de importação e reconciliação por conta."""

import httpx
from asyncpg import Connection

from app.chatwoot_client import Chatwoot
from app.database import lock_primary_contact, record, require_enabled
from app.services import SYSTEM, refresh_contact


async def import_one(conn: Connection, cw: Chatwoot) -> bool:
    """Confirma um contato e seu checkpoint juntos; nunca importa espelhos locais."""
    async with conn.transaction():
        await require_enabled(conn, cw.account)
        job = await conn.fetchrow(
            "SELECT * FROM kb_accounts WHERE account_id=$1", cw.account
        )
        pending = job["import_pending"]
        if not pending:
            response = await cw.request(
                "GET",
                "/contacts",
                params={"page": job["import_page"], "sort": "created_at"},
            )
            pending = [c["id"] for c in response.get("payload", [])]
    if not job["import_pending"]:
        if not pending:
            await conn.execute(
                "UPDATE kb_accounts SET "
                "import_status='complete',import_requested=false,"
                "import_error=NULL,import_attempts=0 WHERE account_id=$1",
                cw.account,
            )
            return False
        await conn.execute(
            "UPDATE kb_accounts SET import_pending=$2,import_page=import_page+1 "
            "WHERE account_id=$1",
            cw.account,
            pending,
        )
    # A página é persistida antes da primeira chamada de contato: falhas não perdem IDs.
    async with conn.transaction():
        await require_enabled(conn, cw.account)
        contact = pending[0]
        if job["import_mode"] == "cards":
            # Funis precedem contato, como na criação e no arquivamento da interface.
            await conn.fetch(
                "SELECT id FROM kb_funnels WHERE account_id=$1 AND "
                "(is_primary OR id=$2) ORDER BY id FOR UPDATE",
                cw.account,
                job["import_funnel_id"],
            )
        await lock_primary_contact(conn, cw.account, contact)
        seen = await conn.fetchval(
            "SELECT 1 FROM kb_import_seen WHERE account_id=$1 AND contact_id=$2",
            cw.account,
            contact,
        )
        missing = False
        if not seen:
            try:
                async with conn.transaction():
                    await refresh_contact(conn, cw, contact)
            except httpx.HTTPStatusError as exc:
                if exc.response.status_code != 404:
                    raise
                missing = True
            if not missing and job["import_mode"] == "cards":
                stage = await conn.fetchrow(
                    """SELECT s.id FROM kb_stages s JOIN kb_funnels f
                    ON (s.account_id,s.funnel_id)=(f.account_id,f.id)
                    WHERE s.account_id=$1 AND s.funnel_id=$2 AND s.id=$3
                    AND NOT s.archived AND NOT f.archived AND s.kind='open' FOR
                    UPDATE OF f,s""",
                    cw.account,
                    job["import_funnel_id"],
                    job["import_stage_id"],
                )
                if not stage:
                    raise ValueError("Destino da importação indisponível")
                exists = await conn.fetchval(
                    "SELECT 1 FROM kb_cards WHERE account_id=$1 AND contact_id=$2 "
                    "AND funnel_id=$3",
                    cw.account,
                    contact,
                    job["import_funnel_id"],
                )
                if not exists:
                    card_id = await conn.fetchval(
                        # O lead nasce no primeiro contato, não no dia da importação.
                        """INSERT INTO
                           kb_cards(account_id,contact_id,funnel_id,stage_id,created_by,
                        conversation_id,conversation_inbox_id,created_at)
                        SELECT
                        account_id,contact_id,$3,$4,$5,conversation_id,inbox_id,
                        least(coalesce(first_seen_at,now()),now())
                        FROM kb_contacts WHERE account_id=$1 AND contact_id=$2
                        RETURNING id""",
                        cw.account,
                        contact,
                        job["import_funnel_id"],
                        job["import_stage_id"],
                        job["import_actor"]["id"],
                    )
                    await record(
                        conn,
                        cw.account,
                        contact,
                        job["import_actor"],
                        "cartao_criado",
                        after={"card_id": card_id},
                        funnel=job["import_funnel_id"],
                        stage=job["import_stage_id"],
                    )
            await record(
                conn,
                cw.account,
                contact,
                job["import_actor"] or SYSTEM,
                "contato_remoto_ausente" if missing else "metadados_importados",
                sync=False,
            )
            await conn.execute(
                "INSERT INTO kb_import_seen(account_id,contact_id,imported) "
                "VALUES($1,$2,$3)",
                cw.account,
                contact,
                not missing,
            )
    # O recibo kb_import_seen foi confirmado com contato/histórico/fila. Se houver
    # queda antes deste resumo, a retomada pula o ID e recalcula o total, sem duplicar.
    await conn.execute(
        """UPDATE kb_accounts SET import_pending=$2,
        imported_count=(SELECT count(*) FROM kb_import_seen WHERE account_id=$1 AND
        imported),
        import_status='running',import_error=NULL,import_attempts=0 WHERE
        account_id=$1""",
        cw.account,
        pending[1:],
    )
    return True


async def reconcile_one(conn: Connection, cw: Chatwoot) -> bool:
    """Percorre contatos locais, recuperando eventos perdidos sem alterar autoridade."""
    async with conn.transaction():
        await require_enabled(conn, cw.account)
        row = await conn.fetchrow(
            "SELECT * FROM kb_accounts WHERE account_id=$1", cw.account
        )
        contact = await conn.fetchval(
            """SELECT contact_id FROM kb_contacts WHERE account_id=$1
            AND contact_id>$2 ORDER BY contact_id LIMIT 1""",
            cw.account,
            row["reconcile_cursor"],
        )
        if contact is not None:
            await lock_primary_contact(conn, cw.account, contact)

            try:
                async with conn.transaction():
                    await refresh_contact(conn, cw, contact)
            except httpx.HTTPStatusError as exc:
                if exc.response.status_code != 404:
                    raise
                # Ausência remota não autoriza apagar o estado local.
                await record(
                    conn,
                    cw.account,
                    contact,
                    SYSTEM,
                    "contato_remoto_ausente",
                    sync=False,
                )
    if contact is None:
        await conn.execute(
            "UPDATE kb_accounts SET reconcile_cursor=0,"
            "reconcile_next_attempt=now()+interval '5 minutes' WHERE account_id=$1",
            cw.account,
        )
        return False
    await conn.execute(
        """UPDATE kb_accounts SET reconcile_cursor=$2,reconcile_error=NULL,
        reconcile_attempts=0 WHERE account_id=$1""",
        cw.account,
        contact,
    )
    return True
