"""Contratos de isolamento e recuperação do adaptador Compose."""

import json

import pytest
from pydantic import ValidationError

from installer.compose import ComposeLifecycle, ComposeRuntime, document, nginx
from installer.config import Deployment
from installer.swarm import InspectionError


def config(**changes):
    return Deployment(
        **{
            "adapter": "compose",
            "name": "kanban-test",
            "context": "local-test",
            "accounts": [1],
            "image": "test@sha256:" + "a" * 64,
            "public_url": "http://localhost:18080",
            "chatwoot_url": "http://rails:3000",
            "chatwoot_service": "rails",
            "chatwoot_database_service": "postgres",
            "chatwoot_project": "cwlab",
            "chatwoot_network": "cwlab_default",
            "network": "cwlab_default",
            "tls": False,
            **changes,
        }
    )


@pytest.mark.parametrize(
    "changes",
    [
        {"chatwoot_project": None},
        {"chatwoot_project": "kanban-test"},
        {"tls": True},
        {"listen_host": "localhost;evil"},
        {"listen_port": 80},
    ],
)
def test_reject_unsafe_compose_contract(changes):
    with pytest.raises(ValidationError):
        config(**changes)


def test_resolve_service_scoped_to_project(monkeypatch):
    r = ComposeRuntime(config())
    calls = []

    def run(*args):
        calls.append(args)
        return b"one\n"

    monkeypatch.setattr(r, "run", run)
    assert r.container("postgres") == "one"
    assert "label=com.docker.compose.project=cwlab" in calls[-1]
    assert r.container("kanban-test_postgres") == "one"
    assert "label=com.docker.compose.project=kanban-test" in calls[-1]


def test_generated_proxy_and_credentials_have_correct_boundaries(tmp_path):
    d = document(config(), "identity", config().image, tmp_path)
    assert d["services"]["nginx"]["ports"] == ["127.0.0.1:18080:80"]
    assert "DATABASE_URL" not in d["services"]["api"]["environment"]
    assert all("deploy" not in s for s in d["services"].values())
    assert d["services"]["api"]["networks"]["public"]["aliases"] == ["kanban-test_api"]
    proxy = nginx(config())
    assert "proxy_buffering off" in proxy and "$http_host" in proxy
    assert "http://rails:3000" in proxy and "http://kanban-test_api:8000" in proxy
    assert "docker.sock" not in json.dumps(d)


def test_secrets_are_private_and_deleted_only_after_down(tmp_path, monkeypatch):
    lc = ComposeLifecycle(config(), tmp_path)
    lc.state.lock()
    try:
        lc.state.save(identity="own", config=config().model_dump())
        lc.resources()
        assert lc.mounts.stat().st_mode & 0o777 == 0o700
        assert all(p.stat().st_mode & 0o777 == 0o600 for p in lc.mounts.iterdir())
        calls = []
        monkeypatch.setattr(lc, "compose", lambda *args: calls.append(args))
        lc.deploy(config().image)
        assert calls[-1] == ("up", "-d", "--no-deps", "postgres")

        def fail(*args):
            raise InspectionError("down falhou")

        monkeypatch.setattr(lc, "compose", fail)
        with pytest.raises(InspectionError):
            lc.remove_services()
        assert lc.mounts.exists()
        monkeypatch.setattr(lc, "compose", lambda *args: calls.append(args))
        lc.remove_services()
        assert calls[-1] == ("down", "--timeout", "30")
        assert not lc.mounts.exists()
        assert (tmp_path / "infrastructure.fernet").exists()
    finally:
        lc.state.close()


def test_failed_migration_does_not_start_api(tmp_path, monkeypatch):
    lc = ComposeLifecycle(config(), tmp_path)
    calls = []

    def fail(*args):
        calls.append(args)
        raise InspectionError("migração falhou")

    monkeypatch.setattr(lc, "compose", fail)
    with pytest.raises(InspectionError):
        lc.migrate_and_start_api()
    assert calls == [("run", "--rm", "--no-deps", "-T", "migrate")]


def test_foreign_project_is_never_adopted(tmp_path, monkeypatch):
    lc = ComposeLifecycle(config(), tmp_path)
    monkeypatch.setattr(lc.runtime, "run", lambda *_args: b"foreign\n")
    monkeypatch.setattr(lc.runtime, "json", lambda *_args: [{"Config": {"Labels": {}}}])
    with pytest.raises(InspectionError, match="alheio"):
        lc.check_services("mine")


def test_legacy_swarm_manifest_defaults_are_compatible(tmp_path, monkeypatch):
    from test_installer_lifecycle import config as swarm_config

    from installer.lifecycle import Lifecycle

    cfg = swarm_config()
    lc = Lifecycle(cfg, tmp_path)
    saved = cfg.model_dump()
    for key in ("adapter", "chatwoot_project", "listen_host", "listen_port"):
        saved.pop(key)
    lc.state.data = {"config": saved, "identity": "previous"}
    monkeypatch.setattr(lc, "check_environment", lambda: None)
    monkeypatch.setattr(lc, "check_services", lambda _identity: None)
    monkeypatch.setattr(lc.runtime, "run", lambda *_args: b"")
    monkeypatch.setattr(
        lc.runtime,
        "rails",
        lambda _request: {
            "accounts": {},
            "receipt": None,
        },
    )
    assert lc.preflight() == {"plans": {}, "receipt": None}


def test_uninstall_does_not_delete_unrecognized_mount_files(tmp_path, monkeypatch):
    lc = ComposeLifecycle(config(), tmp_path)
    lc.state.lock()
    try:
        lc.resources()
        unrelated = lc.mounts / "operator-notes.txt"
        unrelated.write_text("preservar")
        monkeypatch.setattr(lc, "compose", lambda *_args: b"")
        lc.remove_services()
        assert unrelated.read_text() == "preservar"
        assert not (lc.mounts / "database_password").exists()
    finally:
        lc.state.close()
