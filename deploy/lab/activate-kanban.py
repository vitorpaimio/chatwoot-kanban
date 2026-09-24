"""Ativação administrativa exclusiva do laboratório cwlab/kblab, sem logs de tokens."""

import json
import subprocess
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
BASE = ["docker", "--context", "colima-kanban-phase4"]


def run(*args: str, data: str | None = None) -> str:
    """Mantém resultados potencialmente sensíveis em memória."""
    result = subprocess.run(
        [*BASE, *args], input=data, capture_output=True, text=True, timeout=120
    )
    if result.returncode:
        raise SystemExit(
            "Falha na ativação; saída remota omitida por conter credenciais."
        )
    return result.stdout


def container(service: str) -> str:
    """Exige exatamente um container da stack explicitamente selecionada."""
    ids = run(
        "ps", "-q", "--filter", f"label=com.docker.swarm.service.name={service}"
    ).split()
    if len(ids) != 1:
        raise SystemExit("Serviço do laboratório não possui uma réplica disponível.")
    return ids[0]


def main() -> None:
    """Provisiona usuário dedicado e entrega a credencial por pipe para cifragem."""
    from cryptography.fernet import Fernet

    backup = ROOT / ".local/phase4"
    dump = Fernet((backup / "backup.key").read_bytes()).decrypt(
        (backup / "chatwoot-before-kanban.dump.fernet").read_bytes()
    )
    if not dump.startswith(b"PGDMP"):
        raise SystemExit("Backup cifrado não é um dump PostgreSQL válido.")
    rails, api = container("cwlab_rails"), container("kblab_api")
    output = run(
        "exec",
        "-i",
        rails,
        "sh",
        "/run/config/chatwoot-entrypoint.sh",
        "bundle",
        "exec",
        "rails",
        "runner",
        "-",
        data=(ROOT / "deploy/lab/provision-kanban.rb").read_text(),
    )
    lines = [
        s.removeprefix("KANBAN_CREDENTIAL=")
        for s in output.splitlines()
        if s.startswith("KANBAN_CREDENTIAL=")
    ]
    if len(lines) != 1:
        raise SystemExit("Resposta de provisionamento inválida.")
    credential = json.loads(lines[0])
    run(
        "exec",
        "-i",
        api,
        "sh",
        "/run/config/kanban-entrypoint.sh",
        "python",
        "-c",
        (ROOT / "deploy/lab/register-account.py").read_text(),
        data=json.dumps(credential),
    )
    print("Conta 1 registrada; o worker fará o provisionamento dos recursos.")


if __name__ == "__main__":
    main()
