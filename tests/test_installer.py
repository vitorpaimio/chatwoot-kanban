"""Contrato do planejamento sem escrita e sem credenciais no relatório."""

import json
import subprocess

import pytest

from installer import swarm
from installer.__main__ import installation_plan, main


def test_plan_accounts_conflict_reuse_and_no_secrets():
    definition = {
        "id": 18,
        "attribute_key": "kanban_etapa",
        "attribute_model": 1,
        "attribute_display_type": 0,
        "token": "DO_NOT_PRINT",
    }
    inventory = {
        "network": "network_public",
        "accounts": {
            "2": [{**definition, "attribute_display_type": 5}],
            "1": [definition],
        },
    }
    plan = installation_plan(inventory, "network_public")
    assert plan["blocked"]
    assert [a["account_id"] for a in plan["accounts"]] == [1, 2]
    assert plan["accounts"][0]["attributes"][0]["action"] == "reuse"
    assert plan["accounts"][1]["attributes"][0]["action"] == "conflict"
    assert plan["accounts"][0]["attributes"][1]["action"] == "create"
    assert "DO_NOT_PRINT" not in json.dumps(plan)
    assert "ownership" not in json.dumps(plan)
    assert plan == installation_plan(inventory, "network_public")


def test_network_requires_exact_confirmation():
    inventory = {"network": "custom_public", "accounts": {"1": []}}
    assert installation_plan(inventory, "network_public")["blocked"]
    assert installation_plan(inventory, None)["blocked"]
    assert not installation_plan(inventory, "custom_public")["blocked"]


def responses():
    return [
        json.dumps({"LocalNodeState": "active", "ControlAvailable": True}),
        json.dumps([{"Driver": "overlay", "Scope": "swarm"}]),
        json.dumps(
            [
                {
                    "State": {"Running": True},
                    "Config": {
                        "Labels": {
                            "com.docker.swarm.service.name": "chatwoot_rails",
                        }
                    },
                }
            ]
        ),
        'Rails startup\nKANBAN_INVENTORY={"1":[],"2":[]}\n',
    ]


def test_inspect_only_selected_accounts_over_stdin(monkeypatch):
    output = responses()
    calls = []

    def docker(*args, stdin=None):
        calls.append((args, stdin))
        return output.pop(0)

    monkeypatch.setattr(swarm, "docker", docker)
    assert swarm.inspect("network_public", "rails.1.abc", [2, 1, 2]) == {
        "network": "network_public",
        "accounts": {"1": [], "2": []},
    }
    assert calls[-1][0] == (
        "exec",
        "-i",
        "rails.1.abc",
        "bundle",
        "exec",
        "rails",
        "runner",
        "-",
    )
    assert calls[-1][1].startswith("kanban_account_ids = [1, 2]\n")
    assert "SET TRANSACTION READ ONLY" in calls[-1][1]
    assert len(calls) == 4


@pytest.mark.parametrize(
    ("index", "replacement"),
    [
        (0, '{"LocalNodeState":"inactive"}'),
        (0, '{"LocalNodeState":"active","ControlAvailable":false}'),
        (1, '[{"Driver":"bridge","Scope":"local"}]'),
        (2, '[{"State":{"Running":false}}]'),
        (3, 'KANBAN_INVENTORY={"1":[],"3":[]}'),
        (3, "KANBAN_INVENTORY={}\nKANBAN_INVENTORY={}"),
        (3, "invalid-json"),
    ],
)
def test_inspection_fails_closed(monkeypatch, index, replacement):
    output = responses()
    output[index] = replacement
    monkeypatch.setattr(swarm, "docker", lambda *_args, **_kwargs: output.pop(0))
    with pytest.raises(swarm.InspectionError):
        swarm.inspect("network_public", "rails", [1, 2])
    assert len(output) == 3 - index


def test_errors_do_not_echo_process_output(monkeypatch, capsys):
    def fail(*a, **kw):
        raise subprocess.CalledProcessError(1, "docker", stderr="DO_NOT_PRINT")

    monkeypatch.setattr(subprocess, "run", fail)
    monkeypatch.setattr(
        "sys.argv",
        [
            "installer",
            "install",
            "--dry-run",
            "--account",
            "1",
            "--chatwoot-container",
            "rails",
        ],
    )
    assert main() == 2
    captured = capsys.readouterr()
    assert "DO_NOT_PRINT" not in captured.err + captured.out


def test_invalid_account_fails_before_docker(monkeypatch):
    def unexpected(*a, **kw):
        pytest.fail("Docker não deveria ser chamado")

    monkeypatch.setattr(swarm, "docker", unexpected)
    with pytest.raises(swarm.InspectionError):
        swarm.inspect("network_public", "rails", [-1])
