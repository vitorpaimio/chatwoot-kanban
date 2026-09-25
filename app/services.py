from datetime import UTC, datetime
from zoneinfo import ZoneInfo

from app.database import notify, record, require_enabled
from app.provisioning.attributes import provision_attributes, remember_resource

SYSTEM = {"id": None, "name": "Sistema"}
CHATWOOT = {"id": None, "name": "Chatwoot"}
STAGE_ATTRIBUTE = "kanban_etapa"
REMOTE_LOSS_REASON = "Outro: etapa alterada no atributo do contato"
DEFAULT_STAGES = [
    ("Novo", "open"),
    ("Em atendimento", "open"),
    ("Proposta enviada", "open"),
    ("Ganho", "won"),
    ("Perdido", "lost"),
]


def task_state(due, today=None):
    today = today or datetime.now(ZoneInfo("America/Sao_Paulo")).date()
    return "overdue" if due < today else "today" if due == today else "active"


async def projection(conn, account, contact):
    rows = await conn.fetch(
        (
            """
        SELECT c.id, f.name AS funnel, f.is_primary, s.name AS stage FROM
        kb_cards c JOIN kb_funnels f ON
        (f.account_id,f.id)=(c.account_id,c.funnel_id) JOIN kb_stages s ON
        (s.account_id,s.id)=(c.account_id,c.stage_id) WHERE c.account_id=$1
        AND c.contact_id=$2 AND NOT f.archived AND NOT EXISTS
        (SELECT 1 FROM kb_card_deletions d WHERE
         (d.account_id,d.card_id)=(c.account_id,c.id)) ORDER BY c.id DESC
        """
        ),
        account,
        contact,
    )
    last = await conn.fetchval(
        """
        SELECT last_card_id FROM kb_contacts WHERE account_id=$1 AND
        contact_id=$2
        """,
        account,
        contact,
    )
    primary = next((r for r in rows if r["is_primary"]), None)
    recent = next(
        (r for r in rows if r["id"] == last), primary or next(iter(rows), None)
    )
    task = await conn.fetchrow(
        (
            """
        SELECT * FROM kb_tasks WHERE account_id=$1 AND contact_id=$2 AND
        status= 'active'
        """
        ),
        account,
        contact,
    )
    return {
        STAGE_ATTRIBUTE: stage_label(recent["funnel"], recent["stage"])
        if recent
        else None,
        "kanban_tarefa": task["message"] if task else None,
        "kanban_tarefa_vencimento": str(task["due_date"]) if task else None,
    }


def stage_label(funnel: str, stage: str) -> str:
    """Formata a opção da lista do Chatwoot para uma etapa do Kanban."""
    return f"{funnel} / {stage}"


async def stage_options(conn, account: int) -> list[dict]:
    """Lista as etapas ativas na ordem do quadro, com o rótulo do atributo."""
    rows = await conn.fetch(
        """SELECT f.id AS funnel_id,f.name AS funnel,s.id AS stage_id,
        s.name AS stage,s.kind FROM kb_funnels f JOIN kb_stages s ON
        (s.account_id,s.funnel_id)=(f.account_id,f.id) WHERE f.account_id=$1
        AND NOT f.archived AND NOT s.archived
        ORDER BY f.is_primary DESC,f.position,f.id,s.position,s.id""",
        account,
    )
    return [{**r, "label": stage_label(r["funnel"], r["stage"])} for r in rows]


async def sync_stage_options(conn, cw) -> None:
    """Mantém a lista do atributo de etapa igual aos funis e etapas ativos.

    Contas criadas antes da lista têm o atributo como texto; a primeira
    sincronização converte o tipo sem alterar os valores já gravados nos contatos.
    """
    resource = await conn.fetchrow(
        """SELECT remote_id,definition FROM kb_resources WHERE account_id=$1 AND
        resource_type='attribute' AND resource_key=$2""",
        cw.account,
        "contact:" + STAGE_ATTRIBUTE,
    )
    if not resource:
        return
    values = [o["label"] for o in await stage_options(conn, cw.account)]
    definition = resource["definition"] or {}
    if (
        definition.get("attribute_display_type") in ("list", 6)
        and definition.get("attribute_values") == values
    ):
        return
    remote = await cw.request(
        "PATCH",
        f"/custom_attribute_definitions/{resource['remote_id']}",
        json={"attribute_display_type": 6, "attribute_values": values},
    )
    remote = {**definition, **(remote or {}), "id": resource["remote_id"]}
    remote.update(attribute_display_type="list", attribute_values=values)
    await remember_resource(
        conn, cw.account, "attribute", "contact:" + STAGE_ATTRIBUTE, remote, False
    )


async def apply_remote_stage(conn, account: int, contact_id: int, value) -> bool:
    """Leva ao quadro a etapa escolhida na lista do contato no Chatwoot.

    Alterações locais ainda não sincronizadas prevalecem; o valor que o próprio
    Kanban gravou por último não é reaplicado.

    Returns:
        Verdadeiro quando o quadro passou a refletir o valor remoto.
    """
    sync = await conn.fetchrow(
        "SELECT status,projection FROM kb_sync WHERE account_id=$1 AND contact_id=$2",
        account,
        contact_id,
    )
    if sync and sync["status"] != "synced":
        return False
    if sync and (sync["projection"] or {}).get(STAGE_ATTRIBUTE) == value:
        return False
    targets = [o for o in await stage_options(conn, account) if o["label"] == value]
    if len(targets) != 1:
        return False
    target = targets[0]
    card = await conn.fetchrow(
        """SELECT c.* FROM kb_cards c JOIN kb_contacts ct ON
        (ct.account_id,ct.contact_id)=(c.account_id,c.contact_id)
        WHERE c.account_id=$1 AND c.contact_id=$2 AND c.funnel_id=$3
        AND NOT EXISTS (SELECT 1 FROM kb_card_deletions d WHERE
        (d.account_id,d.card_id)=(c.account_id,c.id))
        ORDER BY c.id=ct.last_card_id DESC,c.id DESC LIMIT 1""",
        account,
        contact_id,
        target["funnel_id"],
    )
    reason = REMOTE_LOSS_REASON if target["kind"] == "lost" else None
    if card is None:
        card_id = await conn.fetchval(
            """INSERT INTO kb_cards(account_id,contact_id,funnel_id,stage_id,
            lost_reason,conversation_id,conversation_inbox_id)
            SELECT $1,$2,$3,$4,$5,conversation_id,inbox_id FROM kb_contacts
            WHERE account_id=$1 AND contact_id=$2 RETURNING id""",
            account,
            contact_id,
            target["funnel_id"],
            target["stage_id"],
            reason,
        )
        action = "cartao_criado"
        before, after = None, {"card_id": card_id, "lost_reason": reason}
    else:
        card_id = card["id"]
        action = "cartao_movido"
        before = {
            "stage_id": card["stage_id"],
            "value_cents": card["value_cents"],
            "entered_at": card["stage_entered_at"].isoformat(),
        }
        if card["stage_id"] != target["stage_id"]:
            await conn.execute(
                """UPDATE kb_cards SET stage_id=$3,lost_reason=$4,
                version=version+1,stage_entered_at=now(),position=coalesce(
                (SELECT max(position) FROM kb_cards WHERE account_id=$1
                AND stage_id=$3),0)+1024 WHERE account_id=$1 AND id=$2""",
                account,
                card_id,
                target["stage_id"],
                reason,
            )
        else:
            reason = card["lost_reason"]
        after = {
            "card_id": card_id,
            "stage_id": target["stage_id"],
            "value_cents": card["value_cents"],
            "lost_reason": reason,
        }
    await conn.execute(
        "UPDATE kb_contacts SET last_card_id=$3 WHERE account_id=$1 AND contact_id=$2",
        account,
        contact_id,
        card_id,
    )
    await record(
        conn,
        account,
        contact_id,
        CHATWOOT,
        action,
        before,
        after,
        target["funnel_id"],
        target["stage_id"],
    )
    return True


async def refresh_contact(conn, cw, contact_id, project_cards=True, apply_remote=False):
    """Atualiza metadados do contato e confere o espelho do Kanban.

    Args:
        apply_remote: Aplica a etapa escolhida no Chatwoot. Só eventos de
            webhook usam esta opção; importação e reconciliação não tratam
            espelhos antigos como decisão do usuário.
    """
    account = cw.account
    data = await cw.request("GET", f"/contacts/{contact_id}")
    contact = data.get("payload", data)
    conversations = await cw.request("GET", f"/contacts/{contact_id}/conversations")
    conversations = conversations.get("payload", [])
    # Conversa aberta vence a resolvida: o responsável do card é quem atende agora.
    recent = max(
        conversations,
        key=lambda c: (
            c.get("status") in ("open", "pending"),
            c.get("last_activity_at", 0) or 0,
            c["id"],
        ),
        default={},
    )
    assignee = recent.get("meta", {}).get("assignee") or {}
    contact_labels = await cw.request("GET", f"/contacts/{contact_id}/labels")
    labels = sorted(
        set(contact_labels.get("payload", [])) | set(recent.get("labels") or [])
    )
    attributes = contact.get("custom_attributes") or {}
    activity = contact.get("last_activity_at")
    activity = (
        datetime.fromtimestamp(activity, UTC)
        if isinstance(activity, (int, float))
        else None
    )
    await conn.execute(
        (
            """
        INSERT INTO kb_contacts(account_id,contact_id,name,phone,email,
        thumbnail,labels,assignee_id,assignee_name,conversation_id,last_activity_at,remote_attributes)
        VALUES($1,$2,$3,$4,$5,$6,$7,$8,$9,$10,$11,$12) ON
        CONFLICT(account_id,contact_id) DO UPDATE SET name=excluded.name,
        phone=excluded.phone,email=excluded.email,thumbnail=excluded.thumbnail,
        labels=excluded.labels,assignee_id=excluded.assignee_id,assignee_name=excluded.assignee_name,
        conversation_id=excluded.conversation_id,last_activity_at=excluded.last_activity_at,
        remote_attributes=excluded.remote_attributes
        """
        ),
        account,
        contact_id,
        contact.get("name") or f"Contato {contact_id}",
        contact.get("phone_number"),
        contact.get("email"),
        contact.get("thumbnail"),
        labels,
        assignee.get("id"),
        assignee.get("name"),
        recent.get("id"),
        activity,
        attributes,
    )
    await conn.execute(
        "UPDATE kb_contacts SET inbox_id=$3 WHERE account_id=$1 AND contact_id=$2",
        account,
        contact_id,
        recent.get("inbox_id"),
    )
    # Pin é por cartão. Uma conversa removida perde o vínculo, nunca mantém ACL antiga.
    by_id = {c["id"]: c for c in conversations}
    cards = await conn.fetch(
        "SELECT * FROM kb_cards WHERE account_id=$1 AND contact_id=$2",
        account,
        contact_id,
    )
    for card in cards:
        linked = (
            by_id.get(card["conversation_id"], {})
            if card["conversation_pinned"]
            else recent
        )
        await conn.execute(
            """UPDATE kb_cards SET conversation_id=$3,conversation_inbox_id=$4,
            version=version+CASE WHEN (conversation_id,conversation_inbox_id)
            IS DISTINCT FROM ($3::integer,$4::integer) THEN 1 ELSE 0 END
            WHERE account_id=$1 AND id=$2""",
            account,
            card["id"],
            linked.get("id"),
            linked.get("inbox_id"),
        )
    has_local_state = bool(cards) or await conn.fetchval(
        "SELECT EXISTS(SELECT 1 FROM kb_tasks WHERE account_id=$1 AND contact_id=$2)",
        account,
        contact_id,
    )
    applied = (
        project_cards
        and apply_remote
        and bool(attributes.get(STAGE_ATTRIBUTE))
        and await apply_remote_stage(
            conn, account, contact_id, attributes[STAGE_ATTRIBUTE]
        )
    )
    if project_cards and has_local_state and not applied:
        expected = await projection(conn, account, contact_id)
        if any(attributes.get(k) != v for k, v in expected.items()):
            await record(conn, account, contact_id, SYSTEM, "espelho_divergente")
    await notify(conn, account)


async def setup_account(conn, cw, progress=None):
    await provision_attributes(conn, cw, progress=progress)
    async with conn.transaction():
        await require_enabled(conn, cw.account, ready=False)
        await setup_resources(conn, cw)
    async with conn.transaction():
        await require_enabled(conn, cw.account, ready=False)
        await finish_setup(conn, cw)


async def setup_resources(conn, cw):
    stage_names = [s[0] for s in DEFAULT_STAGES]
    async with conn.transaction():
        funnel = await conn.fetchval(
            (
                """
        INSERT INTO kb_funnels(account_id,name,is_primary) VALUES($1,
        'Funil principal' ,true) ON CONFLICT(account_id) WHERE is_primary DO
        UPDATE SET is_primary=true RETURNING id
        """
            ),
            cw.account,
        )
        exists = await conn.fetchval(
            """
        SELECT count(*) FROM kb_stages WHERE account_id=$1 AND funnel_id=$2
        """,
            cw.account,
            funnel,
        )
        if not exists:
            for i, name in enumerate(stage_names):
                kind = dict(DEFAULT_STAGES).get(name, "open")
                await conn.execute(
                    (
                        """
        INSERT INTO kb_stages(account_id,funnel_id,name,kind,position)
        VALUES($1,$2,$3,$4,$5)
        """
                    ),
                    cw.account,
                    funnel,
                    name,
                    kind,
                    (i + 1) * 1024,
                )
    from app.config import settings
    from app.security import encrypt

    callback_base = (settings.webhook_base_url or settings.public_url).rstrip("/")
    webhook_url = f"{callback_base}/kanban/webhooks/{cw.account}/events"
    response = await cw.request("GET", "/webhooks")
    hooks = response.get("payload", {}).get("webhooks", [])
    hook = next((h for h in hooks if h["url"] == webhook_url), None)
    created_hook = hook is None
    if not hook:
        result = await cw.request(
            "POST",
            "/webhooks",
            json={
                "webhook": {
                    "name": "Kanban integrado",
                    "url": webhook_url,
                    "subscriptions": [
                        "contact_created",
                        "contact_updated",
                        "conversation_created",
                        "conversation_updated",
                        "conversation_status_changed",
                    ],
                }
            },
        )
        hook = result["payload"]["webhook"]
    await remember_resource(
        conn, cw.account, "webhook", webhook_url, hook, created_hook
    )
    await conn.execute(
        """
        UPDATE kb_accounts SET webhook_id=$2,webhook_cipher=$3 WHERE
        account_id=$1
        """,
        cw.account,
        hook["id"],
        encrypt(hook["secret"]),
    )


async def finish_setup(conn, cw):
    await remove_conversation_app(conn, cw)
    await conn.execute(
        (
            """
        UPDATE kb_accounts SET activation_status= 'ready'
        ,activation_error=NULL,activation_attempts=0 WHERE account_id=$1
        """
        ),
        cw.account,
    )
    await notify(conn, cw.account)


async def remove_conversation_app(conn, cw):
    """Remove somente a Dashboard App desta instalação, preservando outras apps."""
    from app.config import settings

    response = await cw.request("GET", "/dashboard_apps")
    apps = response.get("payload", response) if isinstance(response, dict) else response
    urls = {
        f"{settings.public_url}/kanban/?account={cw.account}&compact=1",
        f"{settings.public_url}/kanban?account={cw.account}&compact=1",
    }
    for dashboard in apps:
        content = dashboard.get("content") or []
        if dashboard.get("title") == "Kanban" and any(
            item.get("url") in urls for item in content
        ):
            await cw.request("DELETE", f"/dashboard_apps/{dashboard['id']}")
    await conn.execute(
        "UPDATE kb_accounts SET app_id=NULL WHERE account_id=$1", cw.account
    )
