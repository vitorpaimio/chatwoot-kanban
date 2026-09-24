"""Falhas seguras, isolamento e artefatos duráveis do instalador."""

import json

import pytest
from cryptography.fernet import InvalidToken
from pydantic import ValidationError

from installer.config import Deployment
from installer.lifecycle import Lifecycle
from installer.state import State
from installer.swarm import InspectionError
from installer.template import stack


def config(**changes):
    return Deployment(
        **{
            "name": "test-kanban",
            "context": "local-test",
            "accounts": [2, 1, 2],
            "image": "example/kanban@sha256:" + "a" * 64,
            "public_url": "https://chat.example.com",
            "chatwoot_url": "http://cw_rails:3000",
            "chatwoot_service": "cw_rails",
            "chatwoot_database_service": "cw_postgres",
            "chatwoot_network": "cw_internal",
            **changes,
        }
    )


@pytest.mark.parametrize(
    "changes",
    [
        {"public_url": "https://user:password@example.com"},
        {"public_url": "https://example.com/kanban"},
        {"accounts": [0]},
        {"name": "../foreign"},
        {"rails_wrapper": ["sh", "-c", "echo secret"]},
        {"image": "example:latest"},
        {"chatwoot_database": "db;drop"},
    ],
)
def test_reject_ambiguous_or_sensitive_configuration(changes):
    with pytest.raises(ValidationError):
        config(**changes)


def test_plan_does_not_create_state_or_call_mutations(tmp_path, monkeypatch):
    root = tmp_path / "absent"
    lifecycle = Lifecycle(config(), root)
    monkeypatch.setattr(
        lifecycle,
        "preflight",
        lambda: {
            "plans": {"1": [{"key": "kanban_etapa", "status": "create"}]},
            "receipt": None,
        },
    )
    report = lifecycle.plan("install", "network_public")
    assert not report["blocked"]
    assert not root.exists()
    assert lifecycle.plan("install", "wrong")["blocked"]


def test_state_lock_and_encryption(tmp_path):
    first, second = State(tmp_path), State(tmp_path)
    first.lock()
    try:
        with pytest.raises(InspectionError):
            second.lock()
        first.save_vault({"password": "unique-sensitive-marker"})
        assert first.vault() == {"password": "unique-sensitive-marker"}
        data = (tmp_path / "infrastructure.fernet").read_bytes()
        assert b"unique-sensitive-marker" not in data
        assert (tmp_path / "recovery.key").stat().st_mode & 0o777 == 0o600
        with pytest.raises(InvalidToken):
            first.cipher().decrypt(data[:-10] + b"corruption")
    finally:
        first.close()
    second.lock()
    second.close()


def test_template_scopes_resources_and_has_no_secret_values():
    document = stack(config(), "owner-id", config().image, True)
    assert document["services"]["api"]["deploy"]["replicas"] == 1
    assert document["services"]["migrate"]["deploy"]["replicas"] == 0
    assert (
        document["services"]["postgres"]["deploy"]["labels"][
            "io.chatwoot-kanban.installation"
        ]
        == "owner-id"
    )
    assert (
        document["services"]["api"]["environment"]["WEBHOOK_BASE_URL"]
        == "http://test-kanban_api:8000"
    )
    assert "DATABASE_URL" not in document["services"]["api"]["environment"]
    assert document["services"]["worker"]["healthcheck"]["test"][-2:] == [
        "app.health",
        "worker",
    ]
    assert "password=" not in json.dumps(document)


def test_uninstall_requires_loss_confirmation_before_mutation(tmp_path, monkeypatch):
    lifecycle = Lifecycle(config(), tmp_path)
    monkeypatch.setattr(lifecycle, "preflight", lambda: {})
    monkeypatch.setattr(lifecycle, "stop_app", lambda: pytest.fail("Mutação indevida"))
    with pytest.raises(InspectionError, match="confirm-attribute-data-loss"):
        lifecycle.uninstall("network_public", True, False)
    assert lifecycle.uninstall("network_public", False, False)["idempotent"]


def test_backup_failure_prevents_deployment(tmp_path, monkeypatch):
    lifecycle = Lifecycle(config(), tmp_path)
    lifecycle.state.lock()
    monkeypatch.setattr(lifecycle, "plan", lambda *_args: {"blocked": False})
    monkeypatch.setattr(lifecycle, "stop_app", lambda: None)

    def failed_backup():
        raise InspectionError("Backup falhou")

    monkeypatch.setattr(lifecycle, "backup", failed_backup)
    monkeypatch.setattr(
        lifecycle, "resources", lambda: pytest.fail("Segredos alterados")
    )
    try:
        with pytest.raises(InspectionError, match="Backup falhou"):
            lifecycle.install("install", "network_public")
    finally:
        lifecycle.state.close()


def test_restore_rejects_other_installation(tmp_path, monkeypatch):
    lifecycle = Lifecycle(config(), tmp_path)
    lifecycle.state.lock()
    lifecycle.state.save(identity="one", config=config().model_dump())
    payload = {"manifest": {"identity": "two"}, "dumps": {"kanban": "fake"}}
    (tmp_path / "backup.fernet").write_bytes(
        lifecycle.state.cipher(True).encrypt(json.dumps(payload).encode())
    )
    monkeypatch.setattr(lifecycle, "preflight", lambda: {})
    try:
        with pytest.raises(InspectionError, match="desta instalação"):
            lifecycle.restore("backup.fernet", "network_public")
    finally:
        lifecycle.state.close()


def test_migration_wait_ignores_previous_completed_task(monkeypatch):
    from installer.runtime import Runtime

    runtime = Runtime(config())
    replies = iter([b"old\n", b"new\nold\n"])
    inspected = []
    monkeypatch.setattr(runtime, "run", lambda *_args: next(replies))

    def inspect(*args):
        inspected.append(args[-1])
        return [{"Status": {"State": "complete"}}]

    monkeypatch.setattr(runtime, "json", inspect)
    monkeypatch.setattr("installer.runtime.time.sleep", lambda _seconds: None)
    runtime.wait_job("test_migrate", {"old"})
    assert inspected == ["new"]


def test_status_does_not_trust_stale_heartbeat_when_worker_disabled(
    tmp_path, monkeypatch
):
    lifecycle = Lifecycle(config(), tmp_path)
    monkeypatch.setattr(lifecycle.runtime, "container", lambda _service: "container")
    monkeypatch.setattr(lifecycle.runtime, "run", lambda *_args: b'{"status":"ok"}')
    monkeypatch.setattr(
        lifecycle.runtime,
        "json",
        lambda *_args: [{"Spec": {"Mode": {"Replicated": {"Replicas": 0}}}}],
    )
    assert not lifecycle.status()["healthy"]


def test_runtime_never_echoes_secret_process_output(monkeypatch):
    import subprocess

    from installer.runtime import Runtime

    def failure(*args, **kwargs):
        raise subprocess.CalledProcessError(
            1, args, output=b"token-secret", stderr=b"password-secret"
        )

    monkeypatch.setattr(subprocess, "run", failure)
    with pytest.raises(InspectionError) as error:
        Runtime(config()).run("exec", "container", data=b"service-token")
    assert "secret" not in str(error.value)
    assert "service-token" not in str(error.value)
