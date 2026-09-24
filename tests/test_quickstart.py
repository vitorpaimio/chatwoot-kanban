"""Descoberta sem credenciais e confirmação do instalador de VPS."""

import json

import pytest

from installer import quickstart as q
from installer.state import State
from installer.swarm import InspectionError

IMAGE = "ghcr.io/vitorpaimio/chatwoot-kanban@sha256:" + "a" * 64


def fixture(
    adapter="swarm",
    accounts=None,
    force_ssl=False,
    db_service_net=None,
    frontend_url="https://chat.example.com",
):
    def container(name, command, service, alias):
        labels = (
            {"com.docker.swarm.service.name": service}
            if adapter == "swarm"
            else {
                "com.docker.compose.service": service,
                "com.docker.compose.project": "chatwoot",
            }
        )
        return {
            "Id": name,
            "Name": "/" + name,
            "Config": {"Cmd": command, "Labels": labels},
            "NetworkSettings": {"Networks": {"shared": {"Aliases": [alias]}}},
        }

    rails = container(
        "rails-id",
        ["bundle", "exec", "rails", "server"],
        "cw_rails" if adapter == "swarm" else "rails",
        "rails",
    )
    db = container(
        "db-id",
        ["postgres"],
        "cw_postgres" if adapter == "swarm" else "postgres",
        "postgres",
    )
    worker = container("worker-id", ["bundle", "exec", "sidekiq"], "worker", "worker")
    inventory = {
        "accounts": accounts or [[1, "Principal"]],
        "url": frontend_url,
        "force_ssl": force_ssl,
        "database": {
            "host": "postgres",
            "database": "chatwoot",
            "username": "postgres",
        },
    }
    spec = {
        "Spec": {
            "Labels": {
                "traefik.http.routers.chat.rule": "Host(`chat.example.com`)",
                "traefik.http.routers.chat.entrypoints": "websecure",
                "traefik.swarm.network": "shared",
            }
        }
    }
    objects = {c["Id"]: c for c in (rails, db, worker)}
    calls = []

    def docker(*args, data=None):
        calls.append((args, data))
        if args == ("ps", "-q"):
            return "rails-id\ndb-id\nworker-id\n"
        if args[:2] == ("container", "inspect"):
            return json.dumps([objects[args[2]]])
        if args[:2] == ("service", "inspect"):
            if args[2] == "cw_postgres" and db_service_net:
                task = {"TaskTemplate": {"Networks": [db_service_net]}}
                return json.dumps([{"Spec": {**spec["Spec"], **task}}])
            return json.dumps([spec])
        if args[:2] == ("exec", "-i"):
            return "noise\nKANBAN_DISCOVERY=" + json.dumps(inventory) + "\n"
        raise AssertionError(args)

    return docker, objects, calls


def test_swarm_detects_without_sidekiq_and_requires_no_input(monkeypatch):
    docker, _, calls = fixture()
    monkeypatch.setattr(q, "docker", docker)
    config = q.discover(q.parser().parse_args(["--yes"]), IMAGE)
    assert config.accounts == [1]
    assert config.chatwoot_service == "cw_rails"
    assert config.chatwoot_database_service == "cw_postgres"
    assert config.public_url == "https://chat.example.com"
    assert config.network == "shared"
    assert config.entrypoint == "websecure"
    assert all(call[0][0] in ("ps", "container", "service", "exec") for call in calls)
    assert "READ ONLY" in next(data for _, data in calls if data)


def test_swarm_finds_database_by_alias_declared_only_in_the_service(monkeypatch):
    # O inspect do container pode omitir o alias que o serviço declara na rede.
    docker, objects, _ = fixture(
        db_service_net={"Target": "net-1", "Aliases": ["postgres"]}
    )
    objects["db-id"]["NetworkSettings"]["Networks"]["shared"] = {
        "Aliases": [],
        "DNSNames": ["cw_postgres.1.abc", "db-id"],
        "NetworkID": "net-1",
    }
    monkeypatch.setattr(q, "docker", docker)
    config = q.discover(q.parser().parse_args(["--yes"]), IMAGE)
    assert config.chatwoot_database_service == "cw_postgres"


def test_service_alias_of_another_network_is_not_used(monkeypatch):
    docker, objects, _ = fixture(
        db_service_net={"Target": "outra-rede", "Aliases": ["postgres"]}
    )
    objects["db-id"]["NetworkSettings"]["Networks"]["shared"] = {
        "Aliases": [],
        "NetworkID": "net-1",
    }
    monkeypatch.setattr(q, "docker", docker)
    with pytest.raises(InspectionError, match="PostgreSQL"):
        q.discover(q.parser().parse_args(["--yes"]), IMAGE)


def test_swarm_uses_public_origin_when_rails_forces_ssl(monkeypatch):
    docker, _, _ = fixture(force_ssl=True)
    monkeypatch.setattr(q, "docker", docker)
    config = q.discover(q.parser().parse_args(["--yes"]), IMAGE)
    assert config.chatwoot_url == "https://chat.example.com"
    assert config.public_url == "https://chat.example.com"


def test_swarm_keeps_internal_url_without_force_ssl(monkeypatch):
    docker, _, _ = fixture()
    monkeypatch.setattr(q, "docker", docker)
    config = q.discover(q.parser().parse_args(["--yes"]), IMAGE)
    assert config.chatwoot_url == "http://cw_rails:3000"


def test_swarm_rejects_http_frontend_when_rails_forces_ssl(monkeypatch):
    docker, _, _ = fixture(force_ssl=True, frontend_url="http://chat.example.com")
    monkeypatch.setattr(q, "docker", docker)
    with pytest.raises(InspectionError, match="FORCE_SSL exige FRONTEND_URL HTTPS"):
        q.discover(q.parser().parse_args(["--yes"]), IMAGE)


def test_compose_keeps_internal_url_even_with_force_ssl(monkeypatch):
    docker, _, _ = fixture("compose", force_ssl=True)
    monkeypatch.setattr(q, "docker", docker)
    args = ["--yes", "--public-url", "http://localhost:18080"]
    config = q.discover(q.parser().parse_args(args), IMAGE)
    assert config.chatwoot_url == "http://rails:3000"


def test_multiple_accounts_need_explicit_selection(monkeypatch):
    docker, _, _ = fixture(accounts=[[1, "A"], [2, "B"]])
    monkeypatch.setattr(q, "docker", docker)
    with pytest.raises(InspectionError, match="várias opções"):
        q.discover(q.parser().parse_args(["--yes"]), IMAGE)
    config = q.discover(q.parser().parse_args(["--yes", "--accounts", "2"]), IMAGE)
    assert config.accounts == [2]
    with pytest.raises(InspectionError, match="não existe"):
        q.discover(q.parser().parse_args(["--yes", "--accounts", "3"]), IMAGE)


def test_compose_gateway_does_not_silently_adopt_https(monkeypatch):
    docker, _, _ = fixture("compose")
    monkeypatch.setattr(q, "docker", docker)
    with pytest.raises(InspectionError, match="public-url"):
        q.discover(q.parser().parse_args(["--yes"]), IMAGE)
    config = q.discover(
        q.parser().parse_args(["--yes", "--public-url", "http://localhost:18080"]),
        IMAGE,
    )
    assert config.adapter == "compose"
    assert config.chatwoot_project == "chatwoot"
    assert config.listen_host == "127.0.0.1"
    assert config.listen_port == 18080
    assert config.tls is False


def test_missing_or_wrong_database_is_not_guessed(monkeypatch):
    docker, objects, _ = fixture()
    objects["db-id"]["NetworkSettings"]["Networks"]["shared"]["Aliases"] = ["other"]
    monkeypatch.setattr(q, "docker", docker)
    with pytest.raises(InspectionError, match="PostgreSQL"):
        q.discover(q.parser().parse_args(["--yes"]), IMAGE)


def test_dry_run_and_declined_plan_never_install(monkeypatch, tmp_path):
    docker, _, _ = fixture()
    monkeypatch.setattr(q, "docker", docker)
    monkeypatch.setenv("KANBAN_RUNTIME_IMAGE", IMAGE)
    mutations = []

    class Fake:
        def __init__(self, _config, path):
            self.state = State(path)

        def plan(self, *_args):
            return {"blocked": False}

        def install(self, *args):
            mutations.append(args)

    monkeypatch.setattr(q, "Lifecycle", Fake)
    assert q.run(q.parser().parse_args(["--yes", "--dry-run"]), tmp_path) == 0
    assert not (tmp_path / "installation.json").exists()
    monkeypatch.setattr(q.sys.stdin, "isatty", lambda: True)
    monkeypatch.setattr("builtins.input", lambda _: "n")
    assert q.run(q.parser().parse_args([]), tmp_path) == 0
    assert not mutations
    assert not (tmp_path / "installation.json").exists()


def test_saved_installation_reuses_config_and_update_selects_new_digest(
    monkeypatch, tmp_path
):
    docker, _, _ = fixture()
    monkeypatch.setattr(q, "docker", docker)
    config = q.discover(q.parser().parse_args(["--yes"]), IMAGE)
    (tmp_path / "installation.json").write_text(config.model_dump_json())
    newer = IMAGE[:-64] + "b" * 64
    monkeypatch.setenv("KANBAN_RUNTIME_IMAGE", newer)
    monkeypatch.setattr(
        q, "discover", lambda *_args: pytest.fail("redescoberta indevida")
    )
    images = []
    pulls = []
    monkeypatch.setattr(q, "docker", lambda *args: pulls.append(args))

    class Fake:
        def __init__(self, config, path):
            self.state = State(path)
            images.append(config.image)

        def plan(self, *_args):
            return {"blocked": False}

        def install(self, *_args):
            return {"healthy": True}

    monkeypatch.setattr(q, "Lifecycle", Fake)
    assert q.run(q.parser().parse_args(["--yes"]), tmp_path) == 0
    assert q.run(q.parser().parse_args(["update", "--yes"]), tmp_path) == 0
    assert images == [IMAGE, newer]
    assert pulls == [("pull", IMAGE), ("pull", newer)]
