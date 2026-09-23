from datetime import UTC, date, datetime
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
        "pipeline_01_etapas": primary["stage"] if primary else None,
        "kanban_etapa": f"{recent['funnel']} / {recent['stage']}" if recent else None,
        "kanban_view_mensaje": task["message"] if task else None,
        "kanban_view_fecha_termino": str(task["due_date"]) if task else None,
    }


async def refresh_contact(conn, cw, contact_id, importing=False, project_cards=True):
    account = cw.account
    data = await cw.request("GET", f"/contacts/{contact_id}")
    contact = data.get("payload", data)
    conversations = await cw.request("GET", f"/contacts/{contact_id}/conversations")
    conversations = conversations.get("payload", [])
    recent = max(
        conversations, key=lambda c: c.get("last_activity_at", 0) or 0, default={}
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
    old = await conn.fetchrow(
        "SELECT * FROM kb_contacts WHERE account_id=$1 AND contact_id=$2",
        account,
        contact_id,
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
    if not project_cards:
        return
    funnel = await conn.fetchrow(
        "SELECT * FROM kb_funnels WHERE account_id=$1 AND is_primary", account
    )
    if not funnel:
        return
    stages = await conn.fetch(
        (
            """
        SELECT * FROM kb_stages WHERE account_id=$1 AND funnel_id=$2 AND NOT
        archived ORDER BY position,id
        """
        ),
        account,
        funnel["id"],
    )
    if not stages:
        return
    selected = next(
        (s for s in stages if s["name"] == attributes.get("pipeline_01_etapas")),
        stages[0],
    )
    inserted = await conn.fetchval(
        (
            """
        INSERT INTO kb_cards(account_id,contact_id,funnel_id,stage_id)
        VALUES($1,$2,$3,$4) ON CONFLICT(account_id,funnel_id,contact_id) DO
        NOTHING RETURNING id
        """
        ),
        account,
        contact_id,
        funnel["id"],
        selected["id"],
    )
    pending = await conn.fetchrow(
        "SELECT * FROM kb_sync WHERE account_id=$1 AND contact_id=$2",
        account,
        contact_id,
    )
    previous = old["remote_attributes"] if old else {}
    changed = any(
        attributes.get(key) != previous.get(key)
        for key in (
            "pipeline_01_etapas",
            "kanban_view_mensaje",
            "kanban_view_fecha_termino",
        )
    )
    echo = (
        pending
        and pending["projection"]
        and all(attributes.get(k) == v for k, v in pending["projection"].items())
    )
    if changed and pending and pending["status"] != "synced":
        await record(
            conn,
            account,
            contact_id,
            SYSTEM,
            "conflito_externo",
            previous,
            attributes,
            sync=False,
        )
    elif changed and not echo:
        if not inserted:
            moved = await conn.fetchrow(
                (
                    """
        UPDATE kb_cards SET stage_id=$4,version=version+1,
        stage_entered_at=now() WHERE account_id=$1 AND contact_id=$2 AND
        funnel_id=$3 AND stage_id<>$4 RETURNING id
        """
                ),
                account,
                contact_id,
                funnel["id"],
                selected["id"],
            )
            if moved:
                await record(
                    conn,
                    account,
                    contact_id,
                    SYSTEM,
                    "movimento_externo",
                    previous,
                    attributes,
                    funnel["id"],
                    selected["id"],
                    sync=False,
                )
        message, due = (
            attributes.get("kanban_view_mensaje"),
            attributes.get("kanban_view_fecha_termino"),
        )
        try:
            due = date.fromisoformat(str(due)[:10]) if due else None
        except ValueError:
            due = None
        if message and due:
            await conn.execute(
                (
                    """
        INSERT INTO kb_tasks(account_id,contact_id,message,due_date,due_state)
        VALUES($1,$2,$3,$4,$5) ON CONFLICT(account_id,contact_id) WHERE
        status= 'active' DO UPDATE SET
        message=excluded.message,due_date=excluded.due_date,
        due_state=excluded.due_state,version=kb_tasks.version+1
        """
                ),
                account,
                contact_id,
                str(message),
                due,
                task_state(due),
            )
        elif old and (
            previous.get("kanban_view_mensaje")
            or previous.get("kanban_view_fecha_termino")
        ):
            await conn.execute(
                (
                    """
        UPDATE kb_tasks SET status= 'closed'
        ,closed_at=now(),version=version+1 WHERE account_id=$1 AND
        contact_id=$2 AND status= 'active'
        """
                ),
                account,
                contact_id,
            )
        await record(
            conn,
            account,
            contact_id,
            SYSTEM,
            "atributos_importados" if importing else "alteracao_externa",
            previous,
            attributes,
            sync=False,
        )
    if inserted:
        await record(
            conn,
            account,
            contact_id,
            SYSTEM,
            "contato_importado",
            after={"card_id": inserted},
            funnel=funnel["id"],
            stage=selected["id"],
        )
    await notify(conn, account)


async def setup_account(conn, cw):
    definitions = await cw.request("GET", "/custom_attribute_definitions")
    keys = {a["attribute_key"]: a for a in definitions}
    stage_names = keys.get("pipeline_01_etapas", {}).get("attribute_values") or [
        s[0] for s in DEFAULT_STAGES
    ]
    desired = [
        ("pipeline_01_etapas", "Etapa do Funil principal", 6, stage_names),
        ("kanban_etapa", "Último funil e etapa", 0, []),
        ("kanban_view_mensaje", "Tarefa do Kanban", 0, []),
        ("kanban_view_fecha_termino", "Vencimento da tarefa", 5, []),
    ]
    for key, label, kind, values in desired:
        if key not in keys:
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
    page, count = 1, 0
    while True:
        response = await cw.request("GET", "/contacts", params={"page": page})
        contacts = response.get("payload", [])
        if not contacts:
            break
        for contact in contacts:
            async with conn.transaction():
                await lock_primary_contact(conn, cw.account, contact["id"])
                await refresh_contact(conn, cw, contact["id"], importing=True)
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
        ,activation_error=NULL WHERE account_id=$1
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
