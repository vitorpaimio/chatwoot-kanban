"""Ensaio do bootstrap em runner descartável com Chatwoot real e navegador."""

import json
import os
import subprocess
import time
from pathlib import Path

import httpx

ROOT = Path(__file__).resolve().parents[2]
STATE = Path("/opt/chatwoot-kanban")


def command(
    *args: str, data: str | None = None, timeout: int = 900, public_error: bool = False
) -> str:
    """Não imprime saída de infraestrutura que possa conter credenciais."""
    result = subprocess.run(
        args, input=data, text=True, capture_output=True, timeout=timeout
    )
    if result.returncode:
        detail = result.stderr.strip() if public_error else "Saída privada omitida."
        raise RuntimeError(
            f"Falha na etapa {args[0]} (código {result.returncode}): {detail}"
        )
    return result.stdout


def main() -> None:
    """Testa instalação repetida, saúde, sessão humana e remoção pelo bootstrap."""
    if (
        os.environ.get("GITHUB_ACTIONS") != "true"
        or os.environ.get("KANBAN_DISPOSABLE_CI") != "quickstart"
    ):
        raise SystemExit("Exclusivo do runner descartável quickstart.")
    if STATE.exists():
        raise SystemExit("Estado preexistente: runner não está vazio.")
    image = os.environ["INSTALLER_CANDIDATE"]
    if not image.startswith("ghcr.io/vitorpaimio/chatwoot-kanban:installer-sha-"):
        raise SystemExit("Exige imagem candidata identificada por commit.")
    command("sudo", "mkdir", "-p", str(STATE))
    command("docker", "pull", image)
    command(
        "docker",
        "context",
        "create",
        "colima-kanban-phase42",
        "--docker",
        "host=unix:///var/run/docker.sock",
    )
    env = os.environ.copy()
    env["PHASE42_DISPOSABLE"] = "colima-kanban-phase42"
    env["PYTHONPATH"] = str(ROOT)
    result = subprocess.run(
        ["python", "deploy/compose-lab/prepare.py"],
        env=env,
        capture_output=True,
        timeout=1200,
    )
    if result.returncode:
        raise RuntimeError("Preparo do Chatwoot falhou; saída privada omitida.")
    print("Chatwoot CE preparado.", flush=True)
    rails_id = command(
        "docker",
        "ps",
        "-q",
        "--filter",
        "label=com.docker.compose.project=cwcompose",
        "--filter",
        "label=com.docker.compose.service=rails",
    ).strip()

    def rails(script):
        return command(
            "docker",
            "exec",
            "-i",
            rails_id,
            "/bin/sh",
            "/run/config/chatwoot-entrypoint.sh",
            "bundle",
            "exec",
            "rails",
            "runner",
            "-",
            data=script,
        )

    raw = rails("""
require 'securerandom'
a = Account.create!(name: 'Ensaio Bootstrap')
second = Account.create!(name: 'Segunda conta Bootstrap')
password = 'Aa1!' + SecureRandom.hex(24)
u = User.new(email: 'bootstrap@example.invalid', name: 'Ensaio',
             password: password, password_confirmation: password)
u.skip_confirmation!
u.save!
AccountUser.create!(account: a, user: u, role: :administrator)
AccountUser.create!(account: second, user: u, role: :administrator)
Redis::Alfred.delete(Redis::Alfred::CHATWOOT_INSTALLATION_ONBOARDING)
puts 'HUMAN=' + {email: u.email, password: password}.to_json
""")
    human = json.loads(
        next(line[6:] for line in raw.splitlines() if line.startswith("HUMAN="))
    )
    # Executa o MESMO shell publicado, trocando apenas a tag pelo candidato imutável.
    script = (
        (ROOT / "install.sh")
        .read_text()
        .replace("ghcr.io/vitorpaimio/chatwoot-kanban:installer-master", image)
    )

    def bootstrap(*args):
        return command(
            "sudo", "bash", "-c", script, "install.sh", *args, public_error=True
        )

    print("Verificando dry-run...", flush=True)
    bootstrap(
        "--yes", "--all-accounts", "--dry-run", "--public-url", "http://localhost:18080"
    )
    command("sudo", "test", "!", "-f", str(STATE / "installation.json"))
    print("Instalando pelo shell...", flush=True)
    bootstrap("--yes", "--all-accounts", "--public-url", "http://localhost:18080")
    first = command("sudo", "cat", str(STATE / "state/manifest.json"))
    print("Repetindo instalação...", flush=True)
    bootstrap("--yes")
    second = command("sudo", "cat", str(STATE / "state/manifest.json"))
    assert json.loads(first)["receipt"] == json.loads(second)["receipt"]
    assert '"healthy": true' in bootstrap("status", "--details")
    origin = "http://localhost:18080"
    with httpx.Client(base_url=origin, timeout=30) as client:
        login = client.post("/auth/sign_in", json=human)
        assert login.status_code == 200
        headers = {key: login.headers[key] for key in ("access-token", "client", "uid")}
        assert client.get("/kanban/board?account=1", headers=headers).status_code == 200
        assert client.get("/kanban/board?account=2", headers=headers).status_code == 200
        assert client.get("/kanban/board?account=1").status_code == 401
    command("node", "tests/browser/phase42.cjs", data=json.dumps(human), timeout=120)
    command("node", "tests/browser/installer-loader.cjs", timeout=30)
    print("Sessão humana e quadro real aprovados.", flush=True)
    rails(
        "Account.find(1).contacts.create!(name: 'Contato webhook', "
        "identifier: SecureRandom.uuid)"
    )
    api = "chatwoot-kanban"
    pg = command(
        "docker",
        "ps",
        "-q",
        "--filter",
        f"label=com.docker.compose.project={api}",
        "--filter",
        "label=com.docker.compose.service=postgres",
    ).strip()
    end = time.monotonic() + 60
    while time.monotonic() < end:
        count = command(
            "docker",
            "exec",
            pg,
            "psql",
            "-U",
            "kanban",
            "-d",
            "kanban",
            "-Atc",
            "SELECT count(*) FROM kb_deliveries WHERE status='processed'",
        )
        if int(count) > 0:
            break
        time.sleep(2)
    else:
        raise RuntimeError("Webhook real não processado.")
    bootstrap("update", "--yes")
    assert '"healthy": true' in bootstrap("status", "--details")
    bootstrap("uninstall", "--yes")
    assert (
        command(
            "docker", "ps", "-q", "--filter", f"label=com.docker.compose.project={api}"
        ).strip()
        == ""
    )
    assert (
        command("docker", "inspect", "--format", "{{.State.Running}}", rails_id).strip()
        == "true"
    )
    print(
        "Bootstrap: repetição, navegador, webhook, update e uninstall aprovados.",
        flush=True,
    )


if __name__ == "__main__":
    main()
