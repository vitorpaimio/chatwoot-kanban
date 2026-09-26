"""Origem e campanha pelo anúncio de Click-to-WhatsApp."""

import uuid
from datetime import UTC, datetime, timedelta

from app import maintenance
from app.chatwoot_client import Chatwoot
from app.database import connection
from app.services import AD_SOURCE, ad_referral
from app.worker import process_delivery

REFERRAL = {
    "source_type": "ad",
    "source_id": "120210",
    "headline": "Dr Thiago Virgili",
    "ctwa_clid": "clid-1",
}


def messages(referral=REFERRAL):
    return [
        {"id": 3, "message_type": 1, "content_attributes": {"referral": REFERRAL}},
        {
            "id": 2,
            "message_type": 0,
            "created_at": 1790000000,
            "content_attributes": {"referral": referral} if referral else {},
        },
        {"id": 5, "message_type": 0, "content_attributes": {}},
    ]


class Remote:
    account = 1

    def __init__(self, referral=REFERRAL):
        self.referral = referral

    async def request(self, _method, path, **kwargs):
        if path.startswith("/conversations/"):
            assert kwargs["params"] == {"after": 0}
            return {"payload": messages(self.referral)}
        contact = int(path.split("/")[2])
        if path.endswith("/conversations"):
            return {"payload": [{"id": 700 + contact, "inbox_id": 7, "created_at": 1}]}
        if path.endswith("/labels"):
            return {"payload": []}
        return {"payload": {"id": contact, "name": f"Lead {contact}"}}


async def deliver(contact, remote):
    async with connection() as conn:
        row = await conn.fetchrow(
            """INSERT INTO kb_deliveries(account_id,delivery_id,event_type,
            contact_id,payload) VALUES(1,$1,'conversation_created',$2,$3)
            RETURNING *""",
            str(uuid.uuid4()),
            contact,
            {"id": 700 + contact, "inbox_id": 7, "account": {"id": 1}},
        )
        await process_delivery(conn, remote, row)
        assert (
            await conn.fetchval(
                "SELECT status FROM kb_deliveries WHERE id=$1", row["id"]
            )
            == "processed"
        )


def test_referral_is_first_incoming_ad():
    assert ad_referral(messages())["headline"] == "Dr Thiago Virgili"
    assert ad_referral(messages({"source_type": "post"})) is None
    assert ad_referral(messages(None)) is None


async def test_new_lead_from_ad_gets_origin_on_card(client):
    principal = (await client.get("/kanban/board")).json()["funnels"][0]
    await client.put(
        f"/kanban/funnels/{principal['id']}",
        json={"name": "Principal", "position": 1024, "auto_create": True},
    )
    await deliver(30, Remote())
    await deliver(30, Remote({**REFERRAL, "headline": "Outro anúncio"}))
    async with connection() as conn:
        contact = await conn.fetchrow(
            "SELECT ad_source,ad_campaign,ad_id,ad_click_id FROM kb_contacts "
            "WHERE contact_id=30"
        )
        card = await conn.fetchrow(
            "SELECT source,campaign FROM kb_cards WHERE contact_id=30"
        )
        created = await conn.fetchrow(
            "SELECT e.source,e.campaign FROM kb_card_events e JOIN kb_cards c "
            "ON c.id=e.card_id WHERE c.contact_id=30 AND e.event_type='created'"
        )
    assert tuple(contact) == (AD_SOURCE, "Dr Thiago Virgili", "120210", "clid-1")
    assert tuple(card) == tuple(created) == (AD_SOURCE, "Dr Thiago Virgili")
    options = (await client.get("/kanban/metrics/options")).json()
    assert options["dimensions"] == {"source": True, "campaign": True}


async def test_mapped_attribute_wins_over_ad(client):
    async with connection() as conn:
        await conn.execute(
            """UPDATE kb_accounts SET attribute_mappings=
            '{"origem":"origem","campanha":null,"temperatura":null}'
            WHERE account_id=1"""
        )
        await conn.execute(
            'UPDATE kb_contacts SET remote_attributes=\'{"origem":"Indicação"}\' '
            "WHERE account_id=1 AND contact_id=10"
        )
        await conn.execute(
            "UPDATE kb_contacts SET ad_source=$1,ad_campaign='X' "
            "WHERE account_id=1 AND contact_id=10",
            AD_SOURCE,
        )
        card = await conn.fetchrow(
            "SELECT source,campaign FROM kb_cards WHERE account_id=1 AND contact_id=10"
        )
    assert tuple(card) == ("Indicação", "X")


async def test_repair_fills_ad_origin_for_existing_leads(client, monkeypatch, capsys):
    remote = Remote()

    async def request(_self, method, path, **kw):
        return await remote.request(method, path, **kw)

    async def keep_pool():
        return None

    monkeypatch.setattr(Chatwoot, "request", request)
    monkeypatch.setattr(maintenance, "init_pool", keep_pool)
    monkeypatch.setattr(maintenance, "close_pool", keep_pool)
    args = maintenance.parser().parse_args(["--account", "1", "--ad-origin"])
    await maintenance.main(args)
    await maintenance.main(args)
    out = capsys.readouterr().out
    assert "Aplicado: 1 contatos com origem pelo anúncio" in out
    assert "Aplicado: 0 contatos com origem pelo anúncio" in out
    today = datetime.now(UTC).date()
    sources = await client.get(
        f"/kanban/metrics/sources?start={today - timedelta(days=30)}&end={today}"
    )
    assert sources.status_code == 200, sources.text
    current = sources.json()["current"]
    assert any(
        r["source"] == AD_SOURCE and r["campaign"] == "Dr Thiago Virgili"
        for r in current["rows"]
    )
    async with connection() as conn:
        card = await conn.fetchrow(
            "SELECT source,campaign FROM kb_cards WHERE account_id=1 AND contact_id=10"
        )
        logged = await conn.fetchval(
            "SELECT count(*) FROM kb_history WHERE action='origem_anuncio'"
        )
    assert tuple(card) == (AD_SOURCE, "Dr Thiago Virgili") and logged == 1
