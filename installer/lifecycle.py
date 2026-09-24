"""Ciclo de vida administrativo com backup e recibos de propriedade."""

import base64
import hashlib
import json
import secrets
import time
import uuid
from collections.abc import Callable
from datetime import UTC, datetime
from pathlib import Path

from cryptography.fernet import Fernet

from app.provisioning.attributes import CATALOG, attribute_plan
from installer.config import Deployment
from installer.runtime import Runtime
from installer.state import State, write_private
from installer.swarm import InspectionError
from installer.template import ENTRYPOINT, stack


class Lifecycle:
    """Coordena Swarm, Rails e banco Kanban sem transportar identidade humana."""

    def __init__(self, config: Deployment, directory: Path) -> None:
        self.config = config
        self.state = State(directory)
        self.runtime = Runtime(config)
        self.progress: Callable[[str], None] = lambda _message: None

    def request(self, operation: str, **extras: object) -> dict:
        """Constrói parâmetros do adaptador, sem dados de sessão humana."""
        return {
            "operation": operation,
            "identity": self.state.data.get("identity", "plan"),
            "accounts": self.config.accounts,
            "name": self.config.name,
            **extras,
        }

    def preflight(self) -> dict:
        """Verifica rede, nó único, serviço Rails e definições antes de escrever."""
        runtime = self.runtime
        self.check_environment()
        if self.state.data:
            saved = Deployment.model_validate(self.state.data["config"]).model_dump()
            current = self.config.model_dump()
            saved.pop("image")
            current.pop("image")
            if saved != current:
                raise InspectionError("Configuração imutável difere do manifesto.")
        identity = self.state.data.get("identity")
        self.check_services(identity)
        volumes = (
            runtime.run(
                "volume", "ls", "-q", "--filter", f"name={self.config.name}_data"
            )
            .decode()
            .split()
        )
        if self.config.name + "_data" in volumes:
            labels = (
                runtime.json("volume", "inspect", self.config.name + "_data")[0].get(
                    "Labels"
                )
                or {}
            )
            if (
                not identity
                or labels.get("io.chatwoot-kanban.installation") != identity
            ):
                raise InspectionError(
                    "Volume preexistente não pertence a esta instalação."
                )
        result = runtime.rails(self.request("inspect"))
        plans = {
            account: attribute_plan(definitions, {})
            for account, definitions in result["accounts"].items()
        }
        return {"plans": plans, "receipt": result["receipt"]}

    def check_environment(self) -> None:
        """Valida as pré-condições do adaptador Swarm."""
        runtime = self.runtime
        swarm = runtime.json("info", "--format", "{{json .Swarm}}")
        if swarm.get("LocalNodeState") != "active" or not swarm.get("ControlAvailable"):
            raise InspectionError("É necessário um manager Swarm ativo.")
        # Volumes locais e docker exec exigem o nó certificado. Não inferir HA.
        if len(runtime.run("node", "ls", "-q").decode().split()) != 1:
            raise InspectionError("Este adaptador certifica somente Swarm de nó único.")
        for name in {self.config.network, self.config.chatwoot_network}:
            network = runtime.json("network", "inspect", name)[0]
            if network.get("Driver") != "overlay" or network.get("Scope") != "swarm":
                raise InspectionError("Rede selecionada não é overlay Swarm.")

    def check_services(self, identity: str | None) -> None:
        """Recusa colisões com serviços alheios."""
        runtime = self.runtime
        services = (
            runtime.run(
                "service",
                "ls",
                "-q",
                "--filter",
                f"label=com.docker.stack.namespace={self.config.name}",
            )
            .decode()
            .split()
        )
        for service in services:
            owner = runtime.json("service", "inspect", service)[0]["Spec"].get(
                "Labels", {}
            )
            if not identity or owner.get("io.chatwoot-kanban.installation") != identity:
                raise InspectionError(
                    "Stack preexistente não pertence a este manifesto."
                )

    def plan(
        self, operation: str, confirmation: str | None, purge: bool = False
    ) -> dict:
        """Dry-run não cria chaves, manifesto, usuários ou arquivos temporários."""
        result = self.preflight()
        removals = []
        if operation == "uninstall":
            receipt = result.get("receipt") or {}
            for account, plan in result["plans"].items():
                for item in plan:
                    existing = item.get("existing") or {}
                    own = next(
                        (
                            a
                            for a in receipt.get("attributes", [])
                            if a["account"] == int(account)
                            and a["id"] == existing.get("id")
                            and a["key"] == item.get("mapped_key")
                        ),
                        None,
                    )
                    removals.append(
                        {
                            "account_id": int(account),
                            "key": item["key"],
                            "action": "remove"
                            if purge and own and own["ownership"] == "created"
                            else "preserve",
                        }
                    )
        return {
            "uninstall_attributes": removals,
            "operation": operation,
            "dry_run": True,
            "network": self.config.network,
            "blocked": confirmation != self.config.network
            or any(
                item["status"] == "conflict"
                for plan in result["plans"].values()
                for item in plan
            ),
            "accounts": [
                {
                    "account_id": int(account),
                    "attributes": [
                        {"key": item["key"], "action": item["status"]} for item in plan
                    ],
                }
                for account, plan in result["plans"].items()
            ],
            "purge_attributes": purge,
            "warning": "Remover atributos próprios pode perder valores dos contatos."
            if purge
            else None,
        }

    def backup(self) -> str:
        """Grava dumps e cofre cifrados, sem cópia em claro no disco."""
        r = self.runtime
        c = self.config
        databases = {
            "chatwoot": (
                c.chatwoot_database_service,
                c.chatwoot_database_user,
                c.chatwoot_database,
            )
        }
        local = r.containers(c.name + "_postgres")
        if local:
            databases["kanban"] = (c.name + "_postgres", "kanban", "kanban")
        dumps = {}
        for key, (service, user, database) in databases.items():
            data = r.run(
                "exec",
                r.container(service),
                "pg_dump",
                "-U",
                user,
                "-d",
                database,
                "-Fc",
            )
            if not data.startswith(b"PGDMP"):
                raise InspectionError(
                    "Backup PostgreSQL inválido; operação interrompida."
                )
            dumps[key] = base64.b64encode(data).decode()
        payload = {"schema": 1, "manifest": self.state.data, "dumps": dumps}
        if (self.state.directory / "infrastructure.fernet").exists():
            payload["infrastructure"] = self.state.vault()
        raw = json.dumps(payload).encode()
        cipher = self.state.cipher(create=True)
        encrypted = cipher.encrypt(raw)
        if cipher.decrypt(encrypted) != raw:
            raise InspectionError("Backup não passou na verificação de integridade.")
        name = datetime.now(UTC).strftime("backup-%Y%m%dT%H%M%S-%f.fernet")
        write_private(self.state.directory / name, encrypted)
        backups = list(self.state.data.get("backups", []))
        backups.append(
            {
                "file": name,
                "sha256": hashlib.sha256(encrypted).hexdigest(),
                "databases": sorted(dumps),
            }
        )
        self.state.save(backups=backups)
        return name

    def resources(self) -> None:
        """Cria apenas secrets/configs reservados e identificados pelo manifesto."""
        r, c = self.runtime, self.config
        if not (self.state.directory / "infrastructure.fernet").exists():
            self.state.save_vault(
                {
                    "password": secrets.token_hex(32),
                    "encryption_key": Fernet.generate_key().decode(),
                }
            )
        vault = self.state.vault()
        values = {
            "database_password": vault["password"],
            "encryption_key": vault["encryption_key"],
            "database_url": f"postgresql://kanban:{vault['password']}@{c.name}_postgres:5432/kanban",
        }
        for kind, entries in (
            ("secret", values),
            ("config", {"entrypoint": ENTRYPOINT}),
        ):
            for key, value in entries.items():
                name = c.name + "_" + key
                ids = (
                    r.run(kind, "ls", "-q", "--filter", f"name={name}").decode().split()
                )
                exact = [r.json(kind, "inspect", item)[0] for item in ids]
                exact = [item for item in exact if item["Spec"]["Name"] == name]
                if exact:
                    if (
                        exact[0]["Spec"]
                        .get("Labels", {})
                        .get("io.chatwoot-kanban.installation")
                        != self.state.data["identity"]
                    ):
                        raise InspectionError(
                            "Secret/config preexistente alheio; escolha outro nome."
                        )
                    continue
                r.run(
                    kind,
                    "create",
                    "--label",
                    "io.chatwoot-kanban.installation=" + self.state.data["identity"],
                    name,
                    "-",
                    data=value.encode(),
                )

    def deploy(self, image: str, running: bool = False) -> None:
        """Aplica template sem segredos em argumentos ou arquivos temporários."""
        document = stack(self.config, self.state.data["identity"], image, running)
        self.runtime.run(
            "stack",
            "deploy",
            "--detach=true",
            "--resolve-image",
            "never",
            "-c",
            "-",
            self.config.name,
            data=json.dumps(document).encode(),
        )

    def database_ready(self) -> None:
        """Aguarda saúde do banco antes de dump/migração."""
        r = self.runtime
        deadline = time.monotonic() + 120
        while time.monotonic() < deadline:
            try:
                container = r.container(self.config.name + "_postgres")
                r.run("exec", container, "pg_isready", "-U", "kanban", "-d", "kanban")
                return
            except InspectionError:
                time.sleep(2)
        raise InspectionError("Banco Kanban não ficou pronto.")

    def stop_app(self) -> None:
        """Interrompe mutações locais antes de backup, restauração ou remoção."""
        r = self.runtime
        services = (
            r.run(
                "service",
                "ls",
                "--format",
                "{{.Name}}",
                "--filter",
                f"label=com.docker.stack.namespace={self.config.name}",
            )
            .decode()
            .split()
        )
        targets = [
            name for name in services if name.endswith(("_api", "_worker", "_migrate"))
        ]
        if targets:
            r.run("service", "scale", "--detach=true", *[s + "=0" for s in targets])
            deadline = time.monotonic() + 60
            while time.monotonic() < deadline:
                if all(
                    not r.run(
                        "ps",
                        "-q",
                        "--filter",
                        f"label=com.docker.swarm.service.name={s}",
                    ).strip()
                    for s in targets
                ):
                    return
                time.sleep(2)
            raise InspectionError("Serviços não pararam; nenhuma migração executada.")

    def install(self, operation: str, confirmation: str | None) -> dict:
        """Instala/atualiza retomando recibos; falha não remove recursos alheios."""
        plan = self.plan(operation, confirmation)
        if plan["blocked"]:
            raise InspectionError("Plano bloqueado: confirme rede e resolva conflitos.")
        if operation == "update" and self.state.data.get("status") not in (
            "ready",
            "failed",
        ):
            raise InspectionError("Não há instalação para atualizar.")
        c, r = self.config, self.runtime
        if not self.state.data:
            self.state.save(
                identity=str(uuid.uuid4()), config=c.model_dump(), status="new"
            )
        self.state.save(status="backing_up")
        self.progress("Protegendo seus dados com um backup…")
        self.stop_app()
        self.backup()
        self.state.save(status="installing" if operation == "install" else "updating")
        self.progress("Preparando os serviços do Kanban…")
        self.resources()
        self.deploy(c.image)
        self.database_ready()
        # Inclui o banco preservado de uma desinstalação anterior, antes de migrar.
        self.backup()
        self.migrate_and_start_api()
        api = r.wait_container(c.name + "_api")
        self.progress("Conectando e ativando as contas selecionadas…")
        result = r.rails(
            self.request(
                "install",
                attributes=[a.payload() for a in CATALOG if a.required],
                callback=f"http://{c.name}_api:8000",
            )
        )
        # Token vai diretamente para o banco cifrado; manifesto contém só recibos.
        self.state.save(receipt=result["receipt"])
        r.run(
            "exec",
            "-i",
            api,
            "/bin/sh",
            "/run/config/entrypoint.sh",
            "python",
            "-c",
            Path(__file__).with_name("enroll.py").read_text(),
            data=json.dumps(result).encode(),
        )
        self.start_worker()
        self.progress("Verificando se todas as contas estão prontas para uso…")
        deadline = time.monotonic() + 120
        while time.monotonic() < deadline:
            report = self.status()
            if report["healthy"]:
                self.state.save(status="ready", image=c.image, config=c.model_dump())
                return self.status()
            time.sleep(3)
        raise InspectionError(
            "Serviços não ficaram saudáveis; use status e retome a operação."
        )

    def migrate_and_start_api(self) -> None:
        """Executa uma migração nova antes de disponibilizar a API."""
        c, r = self.config, self.runtime
        previous = set(
            r.run("service", "ps", "-q", c.name + "_migrate").decode().split()
        )
        r.run("service", "scale", "--detach=true", c.name + "_migrate=1")
        r.wait_job(c.name + "_migrate", previous)
        r.run(
            "service",
            "scale",
            "--detach=true",
            c.name + "_migrate=0",
            c.name + "_api=1",
        )

    def start_worker(self) -> None:
        """Ativa processamento somente depois do provisionamento."""
        self.runtime.run(
            "service", "scale", "--detach=true", self.config.name + "_worker=1"
        )

    def check_worker(self) -> None:
        """Recusa heartbeat residual de serviço desativado."""
        spec = self.runtime.json("service", "inspect", self.config.name + "_worker")[0]
        if spec["Spec"]["Mode"]["Replicated"]["Replicas"] == 0:
            raise InspectionError("Worker desativado.")

    def status(self) -> dict:
        """Sonda API, heartbeat do worker e ativação de todas as contas."""
        report = {
            "installation": self.config.name,
            "status": self.state.data.get("status", "absent"),
            "healthy": False,
        }
        try:
            r = self.runtime
            api = r.container(self.config.name + "_api")
            body = r.run(
                "exec",
                api,
                "python",
                "-c",
                "import urllib.request; print(urllib.request.urlopen('http://localhost:8000/health').read().decode())",
            )
            health = json.loads(body)
            self.check_worker()
            worker = r.container(self.config.name + "_worker")
            r.run(
                "exec",
                worker,
                "/bin/sh",
                "/run/config/entrypoint.sh",
                "python",
                "-m",
                "app.health",
                "worker",
            )
            sql = (
                "SELECT count(*) FROM kb_accounts WHERE enabled "
                "AND activation_status='ready' AND account_id IN ("
                + ",".join(map(str, self.config.accounts))
                + ")"
            )
            count = int(
                r.run(
                    "exec",
                    r.container(self.config.name + "_postgres"),
                    "psql",
                    "-U",
                    "kanban",
                    "-d",
                    "kanban",
                    "-Atc",
                    sql,
                )
            )
            report.update(
                healthy=health.get("status") == "ok"
                and count == len(self.config.accounts),
                health=health,
                ready_accounts=count,
            )
        except (InspectionError, ValueError, KeyError):
            report["diagnostic"] = "API, worker ou conta indisponível."
        return report

    def uninstall(
        self, confirmation: str | None, purge: bool, confirm_loss: bool
    ) -> dict:
        """Revoga recursos próprios e remove serviços, preservando volumes."""
        self.preflight()
        if confirmation != self.config.network:
            raise InspectionError("Confirme a rede selecionada.")
        if purge and not confirm_loss:
            raise InspectionError(
                "Confirme a perda de valores com --confirm-attribute-data-loss."
            )
        if not self.state.data or self.state.data.get("status") == "removed":
            return {"status": "removed", "idempotent": True}
        self.state.save(status="backing_up")
        self.stop_app()
        self.backup()
        self.state.save(status="uninstalling")
        result = self.runtime.rails(self.request("uninstall", purge=purge))
        self.remove_services()
        self.state.save(status="removed", receipt=result["receipt"])
        return {"status": "removed", "data": "preserved", "purge_requested": purge}

    def remove_services(self) -> None:
        """Remove infraestrutura própria preservando volume e backups."""
        self.runtime.run("stack", "rm", self.config.name)
        deadline = time.monotonic() + 90
        while time.monotonic() < deadline:
            if not self.runtime.run(
                "service",
                "ls",
                "-q",
                "--filter",
                f"label=com.docker.stack.namespace={self.config.name}",
            ).strip():
                try:
                    for kind in ("secret", "config"):
                        ids = (
                            self.runtime.run(
                                kind,
                                "ls",
                                "-q",
                                "--filter",
                                "label=io.chatwoot-kanban.installation="
                                + self.state.data["identity"],
                            )
                            .decode()
                            .split()
                        )
                        if ids:
                            self.runtime.run(kind, "rm", *ids)
                    break
                except InspectionError:
                    pass
            time.sleep(2)
        else:
            raise InspectionError(
                "Recursos ainda em uso; repita uninstall para finalizar."
            )

    def restore(self, backup: str, confirmation: str | None) -> dict:
        """Restaura o banco Kanban sob parada e preserva o Chatwoot compartilhado."""
        self.preflight()
        if confirmation != self.config.network or Path(backup).name != backup:
            raise InspectionError(
                "Confirme rede e selecione um backup deste diretório."
            )
        payload = json.loads(
            self.state.cipher().decrypt((self.state.directory / backup).read_bytes())
        )
        if (
            payload["manifest"]["identity"] != self.state.data["identity"]
            or "kanban" not in payload["dumps"]
            or not payload["manifest"].get("image")
        ):
            raise InspectionError("Backup não contém o banco desta instalação.")
        self.state.save(status="restoring")
        self.stop_app()
        self.backup()
        dump = base64.b64decode(payload["dumps"]["kanban"], validate=True)
        r = self.runtime
        r.run(
            "exec",
            "-i",
            r.container(self.config.name + "_postgres"),
            "pg_restore",
            "-U",
            "kanban",
            "-d",
            "kanban",
            "--clean",
            "--if-exists",
            "--exit-on-error",
            data=dump,
        )
        image = payload["manifest"].get("image", self.config.image)
        self.deploy(image, running=True)
        self.state.save(status="restored", image=image)
        return {
            "status": "restored",
            "image": image,
            "note": "Confira status; recursos Chatwoot não foram revertidos.",
        }
