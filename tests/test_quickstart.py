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
            "TaskTemplate": {"Networks": [{"Target": "shared-id"}]},
            "Labels": {
                "traefik.http.routers.chat.rule": "Host(`chat.example.com`)",
                "traefik.http.routers.chat.entrypoints": "websecure",
                "traefik.swarm.network": "shared",
            },
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
        if args == ("service", "ls", "-q"):
            return "proxy-id"
        if args[:2] == ("network", "inspect"):
            return json.dumps([{"Name": "shared"}])
        if args[:2] == ("service", "inspect"):
            if args[2] == "proxy-id":
                return json.dumps(
                    [
                        {
                            "Spec": {
                                "TaskTemplate": {
                                    "ContainerSpec": {"Image": "traefik:3.7"},
                                    "Networks": [{"Target": "shared-id"}],
                                }
                            }
                        }
                    ]
                )
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
    assert all(
        call[0][0] in ("ps", "container", "service", "network", "exec")
        for call in calls
    )
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
    monkeypatch.setattr(q.terminal, "interactive", lambda: True)
    monkeypatch.setattr(q.terminal, "select", lambda *_args, **_kwargs: [0])
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


def test_all_accounts_are_explicit_and_mutually_exclusive(monkeypatch):
    docker, _, _ = fixture(accounts=[[3, "C"], [1, "A"], [2, "B"]])
    monkeypatch.setattr(q, "docker", docker)
    config = q.discover(q.parser().parse_args(["--yes", "--all-accounts"]), IMAGE)
    assert config.accounts == [1, 2, 3]
    with pytest.raises(SystemExit):
        q.parser().parse_args(["--accounts", "1", "--all-accounts"])


def test_interactive_selection_uses_names_and_multiple_accounts(monkeypatch):
    docker, _, _ = fixture(accounts=[[1, "Vendas"], [2, "Suporte"], [3, "Filial"]])
    monkeypatch.setattr(q, "docker", docker)
    monkeypatch.setattr(q.terminal, "interactive", lambda: True)

    def select(title, labels, *, multiple=False):
        assert multiple
        assert labels == ["Vendas (#1)", "Suporte (#2)", "Filial (#3)"]
        return [0, 2]

    monkeypatch.setattr(q.terminal, "select", select)
    assert q.discover(q.parser().parse_args([]), IMAGE).accounts == [1, 3]


def test_selected_accounts_reach_activation_and_default_output_is_simple(
    monkeypatch, tmp_path, capsys
):
    docker, _, _ = fixture(accounts=[[1, "Vendas"], [2, "Suporte"]])
    monkeypatch.setattr(q, "docker", docker)
    monkeypatch.setenv("KANBAN_RUNTIME_IMAGE", IMAGE)
    activated = []

    class Fake:
        def __init__(self, config, path):
            self.config = config
            self.state = State(path)

        def plan(self, *_args):
            return {"blocked": False, "technical_plan": "internal-value"}

        def install(self, *_args):
            activated.extend(self.config.accounts)
            return {"healthy": True, "receipt": "internal-value"}

    monkeypatch.setattr(q, "Lifecycle", Fake)
    monkeypatch.setattr(
        q,
        "docker",
        lambda *args, **kwargs: "" if args[0] == "pull" else docker(*args, **kwargs),
    )
    assert q.run(q.parser().parse_args(["--yes", "--all-accounts"]), tmp_path) == 0
    assert activated == [1, 2]
    output = capsys.readouterr().out
    assert "Vendas" in output and "Suporte" in output
    assert "Kanban pronto em 2 conta(s)" in output
    assert "internal-value" not in output and "cw_rails" not in output
    assert "sha256" not in output


def test_unhealthy_status_does_not_claim_ready(monkeypatch, tmp_path, capsys):
    docker, _, _ = fixture()
    monkeypatch.setattr(q, "docker", docker)
    config = q.discover(q.parser().parse_args(["--yes"]), IMAGE)
    (tmp_path / "installation.json").write_text(config.model_dump_json())
    monkeypatch.setenv("KANBAN_RUNTIME_IMAGE", IMAGE)

    class Fake:
        def __init__(self, _config, path):
            self.state = State(path)

        def preflight(self):
            pass

        def status(self):
            return {"healthy": False}

    monkeypatch.setattr(q, "Lifecycle", Fake)
    assert q.run(q.parser().parse_args(["status"]), tmp_path) == 2
    assert "ainda não está pronto" in capsys.readouterr().out
    assert q.run(q.parser().parse_args(["status", "--details"]), tmp_path) == 2
    assert '"healthy": false' in capsys.readouterr().out


def test_interrupt_during_install_records_failure_and_releases_lock(
    monkeypatch, tmp_path
):
    docker, _, _ = fixture()
    monkeypatch.setattr(
        q,
        "docker",
        lambda *args, **kwargs: "" if args[0] == "pull" else docker(*args, **kwargs),
    )
    monkeypatch.setenv("KANBAN_RUNTIME_IMAGE", IMAGE)

    class Fake:
        def __init__(self, _config, path):
            self.state = State(path)

        def plan(self, *_args):
            return {"blocked": False}

        def install(self, *_args):
            self.state.save(status="installing")
            raise KeyboardInterrupt

    monkeypatch.setattr(q, "Lifecycle", Fake)
    with pytest.raises(KeyboardInterrupt):
        q.run(q.parser().parse_args(["--yes"]), tmp_path)
    state = State(tmp_path / "state")
    assert state.data["status"] == "failed"
    state.lock()
    state.close()
