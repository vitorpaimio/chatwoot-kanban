"""Página por etapa e totais completos sobre a mesma seleção autorizada."""

from fastapi.encoders import jsonable_encoder


async def board_page(
    conn,
    account: int,
    funnel_id: int | None,
    stage_id: int | None,
    contact_id: int | None,
    search: str,
    assignee_id: int | None,
    label: str,
    task: str,
    offset: int,
    limit: int,
    card_id: int | None = None,
) -> dict:
    """Aplica filtros antes de agregar e limita a representação de cada coluna."""
    result = await conn.fetchval(
        """
        WITH filtered AS MATERIALIZED (
          SELECT c.*,ct.name,ct.phone,ct.email,ct.thumbnail,ct.labels,
            ct.assignee_id AS contact_assignee_id,ct.assignee_name,
            ct.last_activity_at,t.id AS task_id,t.message,t.due_date,
            t.version AS task_version,t.due_state,t.assigned_to AS task_assigned_to,
            a.name AS task_assignee_name,
            coalesce(s.status,'synced') AS sync_status,s.last_error,
            og.origin_funnel,og.origin_stage,tr.transfer_card_id,tr.transfer_funnel,
            tr.transfer_stage
          FROM kb_visible_cards c JOIN kb_contacts ct USING(account_id,contact_id)
          JOIN kb_funnels f ON (f.account_id,f.id)=(c.account_id,c.funnel_id)
          LEFT JOIN LATERAL (
            SELECT sf.name AS origin_funnel,ss.name AS origin_stage FROM kb_cards o
            JOIN kb_funnels sf ON (sf.account_id,sf.id)=(o.account_id,o.funnel_id)
            JOIN kb_stages ss ON (ss.account_id,ss.id)=(o.account_id,o.stage_id)
            WHERE o.account_id=c.account_id AND o.id=c.origin_card_id
          ) og ON true
          LEFT JOIN LATERAL (
            SELECT d.id AS transfer_card_id,df.name AS transfer_funnel,
              ds.name AS transfer_stage FROM kb_cards d
            JOIN kb_funnels df ON (df.account_id,df.id)=(d.account_id,d.funnel_id)
            JOIN kb_stages ds ON (ds.account_id,ds.id)=(d.account_id,d.stage_id)
            WHERE d.account_id=c.account_id AND d.origin_card_id=c.id
              AND NOT df.archived AND NOT EXISTS (SELECT 1 FROM kb_card_deletions x
              WHERE (x.account_id,x.card_id)=(d.account_id,d.id))
            ORDER BY d.id DESC LIMIT 1
          ) tr ON true
          LEFT JOIN kb_tasks t ON (t.account_id,t.contact_id)=
            (c.account_id,c.contact_id) AND t.status='active'
          LEFT JOIN kb_agents a ON (a.account_id,a.user_id)=
            (t.account_id,t.assigned_to)
          LEFT JOIN kb_sync s ON (s.account_id,s.contact_id)=
            (c.account_id,c.contact_id)
          WHERE c.account_id=$1 AND NOT f.archived
            -- Origem encerrada por transferência só abre pelo próprio id.
            AND (c.transferred_at IS NULL OR c.id=$11)
            AND ($11::bigint IS NULL OR c.id=$11)
            AND ($2::bigint IS NULL OR c.funnel_id=$2)
            AND ($3::bigint IS NULL OR c.stage_id=$3)
            AND ($4::integer IS NULL OR c.contact_id=$4)
            AND ($5='' OR strpos(lower(concat_ws(' ',ct.name,ct.phone,ct.email,
              t.message)),lower($5))>0)
            AND ($6::integer IS NULL OR ct.assignee_id=$6)
            AND ($7='' OR ct.labels ? $7)
            AND ($8='' OR ($8='none' AND t.id IS NULL) OR t.due_state=$8)
        ), ranked AS (
          SELECT *,row_number() OVER(PARTITION BY stage_id ORDER BY position,id)
            AS row_number FROM filtered
        ), totals AS (
          SELECT stage_id,count(*) AS count,coalesce(sum(value_cents),0) AS value_cents
          FROM filtered GROUP BY stage_id
        )
        SELECT jsonb_build_object(
          'cards',coalesce((SELECT jsonb_agg(to_jsonb(r)-'row_number'
            ORDER BY stage_id,position,id) FROM ranked r
            WHERE row_number>$9 AND row_number<=$9+$10),'[]'::jsonb),
          'totals',coalesce((SELECT jsonb_agg(to_jsonb(t)) FROM totals t),'[]'::jsonb),
          'failed_contacts',(SELECT count(DISTINCT contact_id) FROM filtered
            WHERE sync_status='failed'))
        """,
        account,
        funnel_id,
        stage_id,
        contact_id,
        search,
        assignee_id,
        label,
        task,
        offset,
        limit,
        card_id,
    )
    for card in result["cards"]:
        card["assignee_id"] = card.pop("contact_assignee_id")
    for key, table in (("funnels", "kb_funnels"), ("stages", "kb_stages")):
        result[key] = [
            dict(row)
            for row in await conn.fetch(
                f"SELECT * FROM {table} WHERE account_id=$1 AND NOT archived "
                "ORDER BY position,id",
                account,
            )
        ]
    # Contatos são pesquisados no Chatwoot; não baixar o catálogo.
    result["contacts"] = []
    result["offset"], result["limit"] = offset, limit
    result["agents"] = [
        dict(row)
        for row in await conn.fetch(
            "SELECT user_id AS id,name FROM kb_agents "
            "WHERE account_id=$1 ORDER BY name",
            account,
        )
    ]
    return jsonable_encoder(result)
