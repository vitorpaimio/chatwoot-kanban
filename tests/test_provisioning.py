"""Contratos do catálogo e recuperação após criação parcial remota."""

import pytest

from app.provisioning.attributes import (
    CATALOG,
    AttributeConflictError,
    ensure_required_attributes,
)


class Remote:
    def __init__(self, definitions=()):
        self.definitions = list(definitions)
        self.created = []
        self.fail_after = None

    async def request(self, method, path, **kwargs):
        assert path == "/custom_attribute_definitions"
        if method == "GET":
            return list(self.definitions)
        assert method == "POST"
        if self.fail_after == len(self.created):
            raise TimeoutError
        payload = kwargs["json"]
        self.created.append(payload)
        self.definitions.append({"id": len(self.definitions) + 1, **payload})
        return self.definitions[-1]


async def test_empty_account_and_repeat():
    remote = Remote()
    await ensure_required_attributes(remote)
    await ensure_required_attributes(remote)
    assert [d["attribute_key"] for d in remote.created] == [
        a.key for a in CATALOG if a.required
    ]
    assert all(d["attribute_description"] for d in remote.created)


@pytest.mark.parametrize("model,kind", [(1, 0), ("contact_attribute", "text")])
async def test_reuses_contact_even_with_same_conversation_key(model, kind):
    existing = {
        "attribute_key": "kanban_etapa",
        "attribute_model": model,
        "attribute_display_type": kind,
        "attribute_display_name": "Nome alheio",
    }
    remote = Remote(
        [{**existing, "attribute_model": "conversation_attribute"}, existing.copy()]
    )
    await ensure_required_attributes(remote)
    assert remote.definitions[1] == existing
    assert len(remote.created) == 2


@pytest.mark.parametrize(
    "model,kind,reason",
    [
        ("conversation_attribute", "date", "modelo"),
        ("contact_attribute", "text", "tipo"),
    ],
)
async def test_conflict_checked_before_any_creation(model, kind, reason):
    remote = Remote(
        [
            {
                "attribute_key": "kanban_tarefa_vencimento",
                "attribute_model": model,
                "attribute_display_type": kind,
            }
        ]
    )
    with pytest.raises(AttributeConflictError, match=reason):
        await ensure_required_attributes(remote)
    assert remote.created == []


async def test_partial_failure_reuses_previously_created_definition():
    remote = Remote()
    remote.fail_after = 1
    with pytest.raises(TimeoutError):
        await ensure_required_attributes(remote)
    remote.fail_after = None
    await ensure_required_attributes(remote)
    assert len(remote.created) == 3
    assert len({d["attribute_key"] for d in remote.created}) == 3


async def test_internal_callback_keeps_public_url(db, monkeypatch):
    from app.config import settings
    from app.services import setup_resources

    monkeypatch.setattr(settings, "webhook_base_url", "http://proxy-interno/")
    called = []

    class CW:
        account = 1

        async def request(self, method, path, **kwargs):
            assert path == "/webhooks"
            if method == "GET":
                return {"payload": {"webhooks": []}}
            hook = kwargs["json"]["webhook"]
            called.append(hook["url"])
            return {
                "payload": {
                    "webhook": {
                        **hook,
                        "id": 345,
                        "secret": "synthetic-webhook-secret",
                    }
                }
            }

    public = settings.public_url
    async with db.connection() as conn:
        await setup_resources(conn, CW())
        assert (
            await conn.fetchval(
                "SELECT resource_key FROM kb_resources WHERE account_id=1 "
                "AND resource_type='webhook'"
            )
            == "http://proxy-interno/kanban/webhooks/1/events"
        )
    assert called == ["http://proxy-interno/kanban/webhooks/1/events"]
    assert settings.public_url == public
