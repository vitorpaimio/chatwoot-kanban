"""Regressões da VPS: rede do provedor, proxy público e webhook."""

import json
from pathlib import Path

import httpx
import pytest
from test_installer_lifecycle import config

from installer.lifecycle import Lifecycle
from installer.routing import proxy_network
from installer.swarm import InspectionError


def topology(*, labels=None, args=None, env=None, proxy_nets=None):
    rails = {
        "Spec": {
            "Labels": labels or {},
            "TaskTemplate": {
                "Networks": [{"Target": "backend"}, {"Target": "traefik-public"}],
            },
        }
    }
    proxy = {
        "Spec": {
            "TaskTemplate": {
                "ContainerSpec": {
                    "Image": "traefik:v3.7.5",
                    "Args": args or [],
                    "Env": env or [],
                },
                "Networks": [
                    {"Target": name} for name in (proxy_nets or ["traefik-public"])
                ],
            }
        }
    }

    def run(*parts):
        if parts == ("service", "ls", "-q"):
            return "rails proxy"
        if parts[:2] == ("service", "inspect"):
            return json.dumps([rails if parts[2] == "rails" else proxy])
        if parts[:2] == ("network", "inspect"):
            return json.dumps([{"Name": parts[2]}])
        raise AssertionError(parts)

    return run


@pytest.mark.parametrize(
    "args,env",
    [
        (["--providers.swarm.network=traefik-public"], []),
        (["--providers.swarm.network", "traefik-public"], []),
        ([], ["TRAEFIK_PROVIDERS_SWARM_NETWORK=traefik-public"]),
        ([], []),
    ],
)
def test_default_provider_network_never_falls_back_to_database_network(args, env):
    assert proxy_network(topology(args=args, env=env), "rails") == "traefik-public"


def test_explicit_label_must_be_reachable_from_proxy():
    with pytest.raises(InspectionError, match="compartilhada"):
        proxy_network(topology(labels={"traefik.swarm.network": "backend"}), "rails")


def test_ambiguous_networks_fail_closed():
    with pytest.raises(InspectionError, match="ambígua"):
        proxy_network(topology(proxy_nets=["backend", "traefik-public"]), "rails")


def test_service_label_overrides_provider_default_only_when_reachable():
    assert (
        proxy_network(
            topology(
                labels={"traefik.swarm.network": "traefik-public"},
                args=["--providers.swarm.network=backend"],
                proxy_nets=["backend", "traefik-public"],
            ),
            "rails",
        )
        == "traefik-public"
    )


@pytest.mark.parametrize(
    "code,body", [(504, b"timeout"), (200, b"<html>login</html>"), (302, b"")]
)
def test_public_route_rejects_timeout_login_and_redirect(
    tmp_path, monkeypatch, code, body
):
    lc = Lifecycle(config(), tmp_path)
    monkeypatch.setattr(
        httpx, "get", lambda *_args, **_kwargs: httpx.Response(code, content=body)
    )
    with pytest.raises(InspectionError, match="público"):
        lc.check_public_route()


def test_public_route_checks_exact_loader_without_credentials(tmp_path, monkeypatch):
    lc = Lifecycle(config(), tmp_path)
    body = Path("app/static/loader.js").read_bytes()

    def get(url, **kwargs):
        assert url == "https://chat.example.com/kanban/loader.js"
        assert kwargs == {"timeout": 10, "follow_redirects": False, "trust_env": False}
        return httpx.Response(200, content=body)

    monkeypatch.setattr(httpx, "get", get)
    lc.check_public_route()


def test_public_failure_overrides_internal_healthy_status(tmp_path, monkeypatch):
    lc = Lifecycle(config(), tmp_path)
    monkeypatch.setattr(lc.runtime, "container", lambda name: name)
    monkeypatch.setattr(lc, "check_worker", lambda: None)
    monkeypatch.setattr(
        lc.runtime, "run", lambda *args: b"2" if "psql" in args else b'{"status":"ok"}'
    )

    def unreachable():
        raise InspectionError("Proxy fora do ar")

    monkeypatch.setattr(lc, "check_public_route", unreachable)
    assert lc.status()["healthy"] is False


def test_no_loader_or_webhook_is_registered_before_public_route(tmp_path, monkeypatch):
    lc = Lifecycle(config(), tmp_path)
    lc.state.lock()
    monkeypatch.setattr(lc, "plan", lambda *_args: {"blocked": False})
    for method in (
        "stop_app",
        "backup",
        "resources",
        "database_ready",
        "migrate_and_start_api",
    ):
        monkeypatch.setattr(lc, method, lambda: None)
    monkeypatch.setattr(lc, "deploy", lambda *_args: None)
    monkeypatch.setattr(
        lc.runtime,
        "rails",
        lambda *_args: pytest.fail("Chatwoot alterado antes da validação"),
    )

    def unreachable():
        raise InspectionError("Proxy fora do ar")

    monkeypatch.setattr(lc, "wait_public_route", unreachable)
    try:
        with pytest.raises(InspectionError, match="Proxy"):
            lc.install("install", config().network)
    finally:
        lc.state.close()


def test_saved_wrong_network_blocks_before_any_mutation(tmp_path, monkeypatch):
    lc = Lifecycle(config(network="backend"), tmp_path)
    monkeypatch.setattr(
        lc.runtime,
        "json",
        lambda *_args: {
            "LocalNodeState": "active",
            "ControlAvailable": True,
        },
    )
    monkeypatch.setattr(lc.runtime, "run", lambda *_args: b"one-node")
    monkeypatch.setattr(
        "installer.lifecycle.proxy_network", lambda *_args: "traefik-public"
    )
    with pytest.raises(InspectionError, match="rede gravada"):
        lc.check_environment()
    assert not lc.state.manifest.exists()


def test_compose_preserves_local_callback():
    from test_installer_compose import config as compose_config

    from installer.compose import document

    cfg = compose_config()
    rendered = document(cfg, "identity", cfg.image, Path("/tmp/unused"))
    assert cfg.callback_url == "http://kanban-test_api:8000"
    assert (
        rendered["services"]["worker"]["environment"]["WEBHOOK_BASE_URL"]
        == cfg.callback_url
    )
