"""Ensaio real destrutivo, restrito ao laboratório Compose descartável."""

import json
import os
import subprocess
import time
from pathlib import Path

import httpx

from installer.compose import ComposeLifecycle, ComposeRuntime
from installer.config import Deployment

ROOT = Path(__file__).resolve().parents[2]
LOCAL = ROOT / ".local/phase42"
EVENTS = []


def record(name: str, **details: object) -> None:
    """Persiste apenas evidências públicas, sem sessões ou senhas."""
    EVENTS.append({"check": name, **details})
    (ROOT / "docs/phase42-evidence.json").write_text(
        json.dumps(
            {
                "scope": "Compose local ARM64, Chatwoot CE 4.18.0, HTTP/Nginx",
                "checks": EVENTS,
            },
            indent=2,
        )
        + "\n"
    )
    print(name + ": ok", flush=True)


def config(which: str = "one") -> Deployment:
    return Deployment.model_validate_json((LOCAL / f"{which}.json").read_text())


def cli(operation: str, *options: str, which: str = "one", expected: int = 0) -> dict:
    """Exercita CLI pública, sem ecoar saídas sensíveis."""
    result = subprocess.run(
        [
            str(ROOT / ".venv/bin/python"),
            "-m",
            "installer",
            operation,
            "--config",
            str(LOCAL / f"{which}.json"),
            "--state-dir",
            str(LOCAL / which.split("-")[0]),
            "--confirm-network",
            "cwcompose_internal",
            *options,
        ],
        capture_output=True,
        timeout=600,
    )
    if result.returncode != expected:
        # A CLI já suprime respostas remotas, mas o ensaio não as reimprime.
        raise RuntimeError(
            f"{which}/{operation}: código {result.returncode}, esperado {expected}"
        )
    return json.loads(result.stdout) if result.stdout.strip() else {}


def rails(script: str) -> str:
    r = ComposeRuntime(config())
    return r.run(
        "exec",
        "-i",
        r.container("rails"),
        *r.config.rails_wrapper,
        "bundle",
        "exec",
        "rails",
        "runner",
        "-",
        data=script.encode(),
    ).decode()


def sql(statement: str) -> str:
    r = ComposeRuntime(config())
    return (
        r.run(
            "exec",
            r.container("kanban-compose_postgres"),
            "psql",
            "-U",
            "kanban",
            "-d",
            "kanban",
            "-Atc",
            statement,
        )
        .decode()
        .strip()
    )


def ready() -> None:
    end = time.monotonic() + 100
    while time.monotonic() < end:
        lc = ComposeLifecycle(config(), LOCAL / "one")
        if lc.status()["healthy"]:
            return
        time.sleep(2)
    raise RuntimeError("Saúde não recuperada")


def main() -> None:
    """Valida idempotência, sessão humana, falha/restore e remoção seletiva."""
    if os.environ.get("PHASE42_DISPOSABLE") != "colima-kanban-phase42":
        raise SystemExit("Exige laboratório descartável explícito")
    c = config()
    if c.context != "colima-kanban-phase42" or c.chatwoot_project != "cwcompose":
        raise SystemExit("Contexto/projeto não autorizado para ensaio")
    # Senha humana sintética somente na memória; nenhum storageState persistido.
    response = rails("""
require 'securerandom'
a = Account.find_or_create_by!(name: 'Ensaio Compose 4.2')
b = Account.find_or_create_by!(name: 'Outra conta Compose')
u = User.find_or_initialize_by(email: 'phase42@example.invalid')
password = 'Aa1!' + SecureRandom.hex(24)
u.name = 'Administrador de ensaio'
u.password = password
u.password_confirmation = password
u.skip_confirmation!
u.save!
AccountUser.find_or_create_by!(account: a, user: u) { |m| m.role = :administrator }
a.custom_attribute_definitions.find_or_create_by!(
  attribute_key: 'kanban_etapa', attribute_model: 1
) do |v|
  v.attribute_display_name = 'Etapa preexistente'
  v.attribute_display_type = 0
end
Redis::Alfred.delete(Redis::Alfred::CHATWOOT_INSTALLATION_ONBOARDING)
puts 'FIXTURE=' + {email: u.email, password: password, account: a.id}.to_json
""")
    human = json.loads(
        next(line[8:] for line in response.splitlines() if line.startswith("FIXTURE="))
    )
    assert human["account"] == 1
    if os.environ.get("PHASE42_RESUME_AFTER_INSTALL"):
        evidence = json.loads((ROOT / "docs/phase42-evidence.json").read_text())
        assert {"dry_run", "install_repeated"}.issubset(
            {entry["check"] for entry in evidence["checks"]}
        )
        EVENTS.extend(evidence["checks"])
        assert cli("status")["healthy"]
        first = json.loads((LOCAL / "one/manifest.json").read_text())["receipt"]
    else:
        plan = cli("install", "--dry-run")
        assert not plan["blocked"]
        record("dry_run", blocked=False)
        assert cli("install")["healthy"]
        first = json.loads((LOCAL / "one/manifest.json").read_text())["receipt"]
        assert cli("install")["healthy"]
        assert first == json.loads((LOCAL / "one/manifest.json").read_text())["receipt"]
        record("install_repeated", same_receipt=True)

    origin = "http://localhost:18080"
    with httpx.Client(base_url=origin, timeout=30) as client:
        login = client.post(
            "/auth/sign_in", json={k: human[k] for k in ("email", "password")}
        )
        assert login.status_code == 200
        headers = {k: login.headers[k] for k in ("access-token", "client", "uid")}
        assert client.get("/kanban/board?account=1", headers=headers).status_code == 200
        assert client.get("/kanban/board?account=2", headers=headers).status_code == 403
        assert httpx.get(origin + "/kanban/board?account=1").status_code == 401
        browser = subprocess.run(
            ["node", str(ROOT / "tests/browser/phase42.cjs")],
            input=json.dumps(human).encode(),
            capture_output=True,
            timeout=100,
        )
        if browser.returncode:
            raise RuntimeError(browser.stderr.decode().strip())
    record(
        "human_session", board=True, isolation=True, anonymous_denied=True, browser=True
    )

    rails(
        "Account.find(1).contacts.create!(name: 'Contato webhook Compose', "
        "identifier: SecureRandom.uuid)"
    )
    end = time.monotonic() + 50
    while time.monotonic() < end:
        if int(sql("SELECT count(*) FROM kb_deliveries WHERE status='processed'")) > 0:
            break
        time.sleep(2)
    else:
        raise RuntimeError("Webhook real não processado")
    record("webhook", processed=True)

    lc = ComposeLifecycle(config(), LOCAL / "one")
    lc.compose("stop", "worker")
    assert not cli("status", expected=2)["healthy"]
    lc.start_worker()
    ready()
    record("worker_health", stopped_detected=True, recovered=True)

    sql("UPDATE kb_accounts SET processing_limit=17 WHERE account_id=1")
    lc.runtime.run("tag", c.image, "kanban-lab:phase42-update")
    updated = c.model_dump()
    updated["image"] = "kanban-lab:phase42-update"
    (LOCAL / "one-update.json").write_text(json.dumps(updated))
    assert cli("update", which="one-update")["healthy"]
    assert sql("SELECT processing_limit FROM kb_accounts WHERE account_id=1") == "17"
    record("update", data_preserved=True)
    updated["image"] = "kanban-lab:phase42-nonexistent"
    (LOCAL / "one-failure.json").write_text(json.dumps(updated))
    cli("update", which="one-failure", expected=2)
    state = json.loads((LOCAL / "one/manifest.json").read_text())
    assert state["status"] == "failed"
    backup = state["backups"][-1]["file"]
    sql("UPDATE kb_accounts SET processing_limit=23 WHERE account_id=1")
    cli("restore", "--backup", backup, which="one-update")
    ready()
    assert sql("SELECT processing_limit FROM kb_accounts WHERE account_id=1") == "17"
    record("failed_update_restore", data_restored=True, services_healthy=True)

    token_output = rails(
        f"puts 'TOKEN=' + User.find({first['user_id']}).access_token.token"
    )
    token = next(
        line[6:] for line in token_output.splitlines() if line.startswith("TOKEN=")
    )
    cli("uninstall", "--purge-attributes", expected=2)
    assert cli("status")["healthy"]
    cli("uninstall")
    assert cli("uninstall")["idempotent"]
    # Gateway é próprio e já removido; validar revogação dentro da rede Docker.
    probe = """require 'net/http'
u = URI('http://127.0.0.1:3000/api/v1/accounts/1/webhooks')
r = Net::HTTP::Get.new(u)
r['api_access_token'] = JSON.parse(STDIN.read)['token']
puts Net::HTTP.start(u.hostname, u.port) { |h| h.request(r) }.code
"""
    r = lc.runtime
    response = r.run(
        "exec",
        "-i",
        r.container("rails"),
        "ruby",
        "-rjson",
        "-e",
        probe,
        data=json.dumps({"token": token}).encode(),
    )
    assert response.strip() == b"401"
    assert "COUNT=3" in rails(
        "puts 'COUNT=' + Account.find(1).custom_attribute_definitions.count.to_s"
    )
    assert not (LOCAL / "one/mounts").exists()
    assert r.run("volume", "ls", "-q", "--filter", "name=kanban-compose_data").strip()
    record(
        "uninstall_default",
        revoked=True,
        attributes_preserved=True,
        volume_preserved=True,
        repeated=True,
    )
    assert cli("install")["healthy"]
    cli("uninstall", "--purge-attributes", "--confirm-attribute-data-loss")
    result = rails(
        "puts 'COUNT=' + Account.find(1).custom_attribute_definitions.count.to_s"
    )
    # Mesmo manifesto conserva propriedade; apenas o atributo anterior é preservado.
    assert "COUNT=1" in result
    record("reinstall_preserved_volume", healthy=True, preexisting_preserved=True)


if __name__ == "__main__":
    main()
