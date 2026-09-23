from datetime import UTC, datetime
from zoneinfo import ZoneInfo

from app.database import lock_primary_contact, notify, record

SYSTEM = {"id": None, "name": "Sistema"}
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
        AND c.contact_id=$2 AND NOT f.archived
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
    recent = next((r for r in rows if r["id"] == last), primary)
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
        "kanban_etapa": f"{recent['funnel']} / {recent['stage']}" if recent else None,
        "kanban_tarefa": task["message"] if task else None,
        "kanban_tarefa_vencimento": str(task["due_date"]) if task else None,
    }


async def refresh_contact(conn, cw, contact_id, project_cards=True):
    account = cw.account
    data = await cw.request("GET", f"/contacts/{contact_id}")
    contact = data.get("payload", data)
    conversations = await cw.request("GET", f"/contacts/{contact_id}/conversations")
    conversations = conversations.get("payload", [])
    recent = max(
        conversations,
        key=lambda c: (c.get("last_activity_at", 0) or 0, c["id"]),
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
    if project_cards and cards:
        expected = await projection(conn, account, contact_id)
        if any(attributes.get(k) != v for k, v in expected.items()):
            await record(conn, account, contact_id, SYSTEM, "espelho_divergente")
    await notify(conn, account)


async def setup_account(conn, cw):
    definitions = await cw.request("GET", "/custom_attribute_definitions")
    keys = {(a["attribute_key"], a["attribute_model"]): a for a in definitions}
    stage_names = [s[0] for s in DEFAULT_STAGES]
    desired = [
        ("kanban_etapa", "Funil / Etapa", 0, []),
        ("kanban_tarefa", "Tarefa do Kanban", 0, []),
        ("kanban_tarefa_vencimento", "Vencimento da tarefa", 5, []),
    ]
    for key, label, kind, values in desired:
        existing = keys.get((key, "contact_attribute")) or keys.get((key, 1))
        if existing and existing["attribute_display_type"] not in (
            kind,
            {0: "text", 5: "date"}[kind],
        ):
            raise ValueError(f"Tipo incompatível para {key}")
        if not existing and any(a["attribute_key"] == key for a in definitions):
            raise ValueError(f"Modelo incompatível para {key}")
        if not existing:
            await cw.request(
                "POST",
                "/custom_attribute_definitions",
                json={
                    "attribute_key": key,
                    "attribute_display_name": label,
                    "attribute_display_type": kind,
                    "attribute_model": 1,
                    "attribute_values": values,
                },
            )
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

    webhook_url = f"{settings.public_url}/kanban/webhooks/{cw.account}/events"
    response = await cw.request("GET", "/webhooks")
    hooks = response.get("payload", {}).get("webhooks", [])
    hook = next((h for h in hooks if h["url"] == webhook_url), None)
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
    await conn.execute(
        """
        UPDATE kb_accounts SET webhook_id=$2,webhook_cipher=$3 WHERE
        account_id=$1
        """,
        cw.account,
        hook["id"],
        encrypt(hook["secret"]),
    )
    await remove_conversation_app(conn, cw)
    if await conn.fetchval(
        "SELECT import_requested FROM kb_accounts WHERE account_id=$1", cw.account
    ):
        page, count = 1, 0
        while True:
            response = await cw.request("GET", "/contacts", params={"page": page})
            contacts = response.get("payload", [])
            if not contacts:
                break
            for contact in contacts:
                async with conn.transaction():
                    await lock_primary_contact(conn, cw.account, contact["id"])
                    await refresh_contact(conn, cw, contact["id"])
                count += 1
                await conn.execute(
                    "UPDATE kb_accounts SET imported_count=$2 WHERE account_id=$1",
                    cw.account,
                    count,
                )
            page += 1
    await conn.execute(
        (
            """
        UPDATE kb_accounts SET activation_status= 'ready'
        ,activation_error=NULL,import_requested=false WHERE account_id=$1
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
