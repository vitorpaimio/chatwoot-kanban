"""Prepara exclusivamente o laboratório opt-in Compose da fase 4.2."""

import json
import os
import secrets
import subprocess
from pathlib import Path

import yaml

from installer.state import write_private

ROOT = Path(__file__).resolve().parents[2]
LOCAL = ROOT / ".local/phase42"


def main() -> None:
    """Gera Compose descartável sem credenciais fixas e prepara banco Chatwoot."""
    if os.environ.get("PHASE42_DISPOSABLE") != "colima-kanban-phase42":
        raise SystemExit("Exige PHASE42_DISPOSABLE=colima-kanban-phase42")
    LOCAL.mkdir(mode=0o700, parents=True, exist_ok=True)
    LOCAL.chmod(0o700)
    source = yaml.safe_load((ROOT / "deploy/lab/stack.yml").read_text())
    source.pop("version", None)
    source.pop("x-chatwoot", None)
    source["name"] = "cwcompose"
    source["services"].pop("proxy")
    source["networks"] = {"internal": {"driver": "bridge"}}
    source["configs"] = {
        "chatwoot_entrypoint": {"file": str(ROOT / "deploy/lab/chatwoot-entrypoint.sh")}
    }
    for service in source["services"].values():
        service.pop("deploy", None)
    for name in ("cw_lab_db_password", "cw_lab_secret_key_base"):
        path = LOCAL / name
        if not path.exists():
            write_private(path, secrets.token_hex(64).encode())
        source["secrets"][name] = {"file": str(path)}
    write_private(LOCAL / "chatwoot.json", json.dumps(source).encode())
    config = {
        "adapter": "compose",
        "name": "kanban-compose",
        "context": "colima-kanban-phase42",
        "accounts": [1],
        "image": "kanban-lab:phase42",
        "allow_local_image": True,
        "public_url": "http://localhost:18080",
        "chatwoot_url": "http://rails:3000",
        "chatwoot_project": "cwcompose",
        "chatwoot_service": "rails",
        "chatwoot_database_service": "postgres",
        "chatwoot_network": "cwcompose_internal",
        "network": "cwcompose_internal",
        "rails_wrapper": ["/bin/sh", "/run/config/chatwoot-entrypoint.sh"],
        "tls": False,
        "listen_port": 18080,
    }
    write_private(LOCAL / "one.json", json.dumps(config).encode())
    command = [
        "docker",
        "--context",
        config["context"],
        "compose",
        "-p",
        "cwcompose",
        "-f",
        str(LOCAL / "chatwoot.json"),
    ]
    for args in [
        ("up", "-d", "--wait", "postgres", "redis"),
        ("run", "--rm", "--no-deps", "-T", "prepare"),
        ("up", "-d", "--no-deps", "rails", "sidekiq"),
    ]:
        result = subprocess.run(command + list(args), capture_output=True, timeout=900)
        if result.returncode:
            raise SystemExit("Falha preparando Chatwoot; saída omitida.")
        print("Chatwoot: etapa " + args[0] + " concluída", flush=True)


if __name__ == "__main__":
    main()
