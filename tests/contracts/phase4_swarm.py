"""Ensaio destrutivo opt-in: somente o laboratório Colima da Fase 4."""

import json
import os
import subprocess
import time
from pathlib import Path

import httpx

from installer.config import Deployment
from installer.runtime import Runtime

ROOT = Path(__file__).resolve().parents[2]
DIRECTORY = ROOT / ".local/phase4-cert"
EVENTS = []


def record(name: str, **data: object) -> None:
    """Registra apenas evidências sem credenciais."""
    EVENTS.append({"check": name, **data})
    (DIRECTORY / "progress.json").write_text(json.dumps(EVENTS, indent=2))
    print(json.dumps(EVENTS[-1]), flush=True)


def cli(which: str, operation: str, *options: str, expected: int = 0) -> dict:
    """Exercita a CLI pública com stdout/stderr capturados."""
    result = subprocess.run(
        [
            str(ROOT / ".venv/bin/python"),
            "-m",
            "installer",
            operation,
            "--config",
            str(DIRECTORY / f"{which}.json"),
            "--state-dir",
            str(DIRECTORY / which.split("-")[0]),
            "--confirm-network",
            "network_public",
            *options,
        ],
        cwd=ROOT,
        capture_output=True,
        text=True,
        timeout=400,
    )
    if result.returncode != expected:
        raise RuntimeError(
            f"Falha no ensaio {which}/{operation}: código {result.returncode}"
        )
    return json.loads(result.stdout) if result.stdout.strip() else {}


def runtime(which: str) -> Runtime:
    return Runtime(
        Deployment.model_validate_json((DIRECTORY / f"{which}.json").read_text())
    )


def sql(which: str, statement: str) -> str:
    """Consulta banco exclusivo de uma instalação de ensaio."""
    r = runtime(which)
    return (
        r.run(
            "exec",
            r.container(r.config.name + "_postgres"),
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


def rails(script: str) -> str:
    """Opera somente o Chatwoot descartável; não registra a saída arbitrária."""
    r = runtime("one")
    return r.run(
        "exec",
        "-i",
        r.container(r.config.chatwoot_service),
        *r.config.rails_wrapper,
        "bundle",
        "exec",
        "rails",
        "runner",
        "-",
        data=script.encode(),
    ).decode()


def ready(which: str) -> None:
    """Aguarda saúde real depois de restaurar ou reiniciar worker."""
    end = time.monotonic() + 100
    while time.monotonic() < end:
        result = subprocess.run(
            [
                str(ROOT / ".venv/bin/python"),
                "-m",
                "installer",
                "status",
                "--config",
                str(DIRECTORY / f"{which}.json"),
                "--state-dir",
                str(DIRECTORY / which),
            ],
            capture_output=True,
            cwd=ROOT,
            timeout=120,
        )
        if result.returncode == 0:
            return
        time.sleep(3)
    raise RuntimeError("Serviços não recuperaram saúde")


def main() -> None:
    """Executa repetição, duas instalações, falha, restore e ambas remoções."""
    if os.environ.get("PHASE4_DISPOSABLE_SWARM") != "colima-kanban-phase4":
        raise SystemExit("Exige PHASE4_DISPOSABLE_SWARM=colima-kanban-phase4")
    for which in ("one", "two"):
        r = runtime(which)
        if (
            r.config.context != "colima-kanban-phase4"
            or r.config.chatwoot_service != "cwlab_rails"
        ):
            raise SystemExit("Contexto de laboratório obrigatório")
    if os.environ.get("PHASE4_RESUME_AFTER_SETUP"):
        EVENTS.extend(json.loads((DIRECTORY / "setup-evidence.json").read_text()))
    else:
        assert cli("one", "status")["healthy"]
        initial = json.loads((DIRECTORY / "one/manifest.json").read_text())["receipt"]
        assert cli("one", "install")["healthy"]
        after = json.loads((DIRECTORY / "one/manifest.json").read_text())["receipt"]
        assert initial == after
        record("repeated_install", same_resources=True)

        conflict = cli("two", "install", "--dry-run", expected=2)
        assert conflict["blocked"] and not (DIRECTORY / "two").exists()
        record("required_conflict", blocked_without_state=True)
        rails(
            "Account.find(2).custom_attribute_definitions.find_by!(attribute_key:'kanban_etapa').update!(attribute_display_type:0)"
        )
        assert cli("two", "install")["healthy"]
        assert cli("one", "status")["healthy"]
        record("two_installations", healthy=True)
    for host in ("localhost", "127.0.0.1"):
        deadline = time.monotonic() + 40
        while time.monotonic() < deadline:
            response = httpx.get(f"http://{host}:18080/kanban", timeout=10)
            if response.status_code == 200 and "Quadro Kanban" in response.text:
                break
            time.sleep(2)
        else:
            raise RuntimeError("Proxy não convergiu para a aplicação")
    record("traefik_proxy", both_origins=True)

    r = runtime("one")
    r.run("service", "scale", "--detach=true", r.config.name + "_worker=0")
    time.sleep(5)
    assert not cli("one", "status", expected=2)["healthy"]
    r.run("service", "scale", "--detach=true", r.config.name + "_worker=1")
    ready("one")
    record("worker_health", stopped_detected=True, recovered=True)

    sql("one", "UPDATE kb_accounts SET processing_limit=17 WHERE account_id=1")
    r.run("tag", r.config.image, "kanban-lab:phase4-update")
    updated = r.config.model_dump()
    updated["image"] = "kanban-lab:phase4-update"
    (DIRECTORY / "one-update.json").write_text(json.dumps(updated))
    assert cli("one-update", "update")["healthy"]
    assert (
        sql("one", "SELECT processing_limit FROM kb_accounts WHERE account_id=1")
        == "17"
    )
    record("update", settings_preserved=True)

    updated["image"] = "kanban-lab:phase4-nonexistent"
    (DIRECTORY / "one-failure.json").write_text(json.dumps(updated))
    cli("one-failure", "update", expected=2)
    state = json.loads((DIRECTORY / "one/manifest.json").read_text())
    assert state["status"] == "failed"
    assert any("kanban" in b["databases"] for b in state["backups"])
    backup = state["backups"][-1]["file"]
    sql("one", "UPDATE kb_accounts SET processing_limit=23 WHERE account_id=1")
    cli("one-update", "restore", "--backup", backup)
    ready("one")
    assert (
        sql("one", "SELECT processing_limit FROM kb_accounts WHERE account_id=1")
        == "17"
    )
    record("failed_update_restore", previous_settings_restored=True)

    assert cli("one-update", "install")["healthy"]
    state = json.loads((DIRECTORY / "one/manifest.json").read_text())
    user = state["receipt"]["user_id"]
    token_output = rails(f"puts 'PROBE_TOKEN=' + User.find({user}).access_token.token")
    token = next(
        line.split("=", 1)[1]
        for line in token_output.splitlines()
        if line.startswith("PROBE_TOKEN=")
    )
    cli("one-update", "uninstall")
    response = httpx.get(
        "http://localhost:18080/api/v1/accounts/1/webhooks",
        headers={"api_access_token": token},
        timeout=20,
    )
    assert response.status_code == 401
    assert "PROBE=3" in rails(
        "puts 'PROBE=' + Account.find(1).custom_attribute_definitions.where("
        "attribute_key:%w[kanban_etapa kanban_tarefa kanban_tarefa_vencimento],"
        "attribute_model:1).count.to_s"
    )
    assert cli("two", "status")["healthy"]
    assert cli("one-update", "uninstall")["idempotent"]
    record(
        "uninstall_default",
        token_revoked=True,
        preexisting_attributes_preserved=True,
        other_installation_healthy=True,
        repeated=True,
    )

    cli("two", "uninstall", "--purge-attributes", expected=2)
    assert cli("two", "status")["healthy"]
    cli("two", "uninstall", "--purge-attributes", "--confirm-attribute-data-loss")
    result = rails(
        "a=Account.find(2).custom_attribute_definitions; "
        "puts 'PROBE=' + a.where(attribute_key:'kanban_etapa').count.to_s + ':' + "
        "a.where(attribute_key:%w[kanban_tarefa kanban_tarefa_vencimento]).count.to_s; "
        "puts 'LOADER=' + InstallationConfig.find_by(name:'DASHBOARD_SCRIPTS')"
        ".value.to_s.include?('data-chatwoot-kanban').to_s"
    )
    assert "PROBE=1:0" in result and "LOADER=false" in result
    record(
        "uninstall_purge",
        confirmation_required=True,
        owned_removed=True,
        preexisting_preserved=True,
        loader_removed=True,
    )
    path = ROOT / "docs/phase4-evidence.json"
    path.write_text(
        json.dumps(
            {"scope": "Swarm single-node ARM64, Chatwoot CE 4.18.0", "checks": EVENTS},
            indent=2,
        )
        + "\n"
    )


if __name__ == "__main__":
    main()
