"""Inspeção somente leitura do Swarm e das contas selecionadas no Chatwoot."""

import json
import re
import subprocess
from pathlib import Path


class InspectionError(RuntimeError):
    """Falha de inspeção com diagnóstico seguro para o operador."""


def docker(*args: str, stdin: str | None = None) -> str:
    """Executa Docker sem shell e sem propagar saída de erro potencialmente sensível."""
    try:
        result = subprocess.run(
            ["docker", *args],
            input=stdin,
            capture_output=True,
            text=True,
            check=True,
            timeout=90,
        )
    except (OSError, subprocess.SubprocessError):
        raise InspectionError("Inspeção Docker falhou; verifique acesso e recursos.")
    return result.stdout


def inspect(network: str, container: str, accounts: list[int]) -> dict:
    """Verifica manager, rede overlay e container Rails local antes da consulta."""
    for name in (network, container):
        if not re.fullmatch(r"[a-zA-Z0-9][a-zA-Z0-9_.-]{0,127}", name):
            raise InspectionError("Nome de rede ou container inválido.")
    if not accounts or any(
        type(account) is not int or account <= 0 for account in accounts
    ):
        raise InspectionError("Selecione IDs de contas positivos.")
    try:
        swarm = json.loads(docker("info", "--format", "{{json .Swarm}}"))
        if swarm.get("LocalNodeState") != "active" or not swarm.get("ControlAvailable"):
            raise InspectionError("Execute em um manager Swarm ativo.")
        net = json.loads(docker("network", "inspect", network))[0]
        if net.get("Driver") != "overlay" or net.get("Scope") != "swarm":
            raise InspectionError("A rede pública precisa ser overlay do Swarm.")
        task = json.loads(docker("container", "inspect", container))[0]
        labels = task.get("Config", {}).get("Labels") or {}
        if not task.get("State", {}).get("Running") or not labels.get(
            "com.docker.swarm.service.name"
        ):
            raise InspectionError("Selecione um container Rails ativo deste Swarm.")
        script = Path(__file__).with_name("inventory.rb").read_text()
        script = (
            "kanban_account_ids = " + json.dumps(sorted(set(accounts))) + "\n" + script
        )
        output = docker(
            "exec",
            "-i",
            container,
            "bundle",
            "exec",
            "rails",
            "runner",
            "-",
            stdin=script,
        )
        marker = "KANBAN_INVENTORY="
        lines = [
            line[len(marker) :]
            for line in output.splitlines()
            if line.startswith(marker)
        ]
        if len(lines) != 1:
            raise InspectionError("Chatwoot não retornou um inventário único.")
        inventory = json.loads(lines[0])
        if not isinstance(inventory, dict) or set(inventory) != {
            str(a) for a in accounts
        }:
            raise InspectionError("Inventário não corresponde às contas selecionadas.")
        return {"network": network, "accounts": inventory}
    except (ValueError, KeyError, IndexError, TypeError, AttributeError):
        raise InspectionError(
            "Resposta de inspeção inválida; nenhuma escrita executada."
        )
