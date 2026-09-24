"""Adaptador Compose/Nginx que reutiliza o ciclo de vida e os recibos."""

import json
import secrets
from pathlib import Path
from urllib.parse import urlsplit

from cryptography.fernet import Fernet

from installer.config import Deployment
from installer.lifecycle import Lifecycle
from installer.runtime import Runtime
from installer.state import write_private
from installer.swarm import InspectionError
from installer.template import ENTRYPOINT, stack

OWNER = "io.chatwoot-kanban.installation"
DROP = """import os, sys, pwd
os.environ["HOME"] = pwd.getpwuid(10001).pw_dir
os.setgroups([])
os.setgid(10001)
os.setuid(10001)
os.execvp(sys.argv[1], sys.argv[1:])
"""


def nginx(config: Deployment) -> str:
    """Encaminha a mesma origem e mantém SSE e WebSocket sem buffering."""
    return """map $http_upgrade $connection_upgrade {
    default upgrade;
    '' close;
}
server {
    listen 80;
    server_name _;
    resolver 127.0.0.11 valid=5s ipv6=off;
    client_max_body_size 40m;
    proxy_set_header Host $http_host;
    proxy_set_header X-Forwarded-Host $http_host;
    proxy_set_header X-Forwarded-Proto $scheme;
    proxy_set_header X-Forwarded-For $proxy_add_x_forwarded_for;
    proxy_set_header Upgrade $http_upgrade;
    proxy_set_header Connection $connection_upgrade;
    proxy_http_version 1.1;
    proxy_read_timeout 3600s;
    proxy_buffering off;
    location ~ ^/kanban(?:/|$) {
        set $kanban http://API:8000;
        proxy_pass $kanban;
    }
    location / {
        set $chatwoot CHATWOOT;
        proxy_pass $chatwoot;
    }
}
""".replace("API", config.name + "_api").replace(
        "CHATWOOT", config.chatwoot_url.rstrip("/")
    )


def document(config: Deployment, identity: str, image: str, directory: Path) -> dict:
    """Renderiza Compose sem valores secretos; mounts privados são duráveis."""
    result = stack(config, identity, image)
    result.pop("version")
    result["name"] = config.name
    result["networks"]["private"] = {"driver": "bridge", "labels": {OWNER: identity}}
    for name, service in result["services"].items():
        service.pop("deploy")
        service["labels"] = {OWNER: identity}
        service["restart"] = "no" if name == "migrate" else "unless-stopped"
        service["networks"] = {
            key: {"aliases": [config.name + "_" + name]} for key in service["networks"]
        }
        if name != "postgres":
            # Bind secrets Compose não respeitam uid/gid: bootstrap lê como root,
            # depois executa a aplicação como o usuário original da imagem.
            service["user"] = "0:0"
            service["configs"].append(
                {"source": "drop", "target": "/run/config/drop.py"}
            )
    result["services"]["nginx"] = {
        "image": "nginx:1.28-alpine",
        "labels": {OWNER: identity},
        "restart": "unless-stopped",
        "ports": [f"{config.listen_host}:{config.listen_port}:80"],
        "networks": (
            ["public"]
            if config.network == config.chatwoot_network
            else ["public", "chatwoot"]
        ),
        "configs": [{"source": "nginx", "target": "/etc/nginx/conf.d/default.conf"}],
        "healthcheck": {
            "test": ["CMD-SHELL", "wget -q -O /dev/null http://127.0.0.1/api"],
            "interval": "10s",
            "timeout": "5s",
            "retries": 6,
        },
    }
    result["configs"] = {
        key: {"file": str(directory / filename)}
        for key, filename in {
            "entrypoint": "entrypoint.sh",
            "drop": "drop.py",
            "nginx": "nginx.conf",
        }.items()
    }
    result["secrets"] = {
        key: {"file": str(directory / key)} for key in result["secrets"]
    }
    return result


class ComposeRuntime(Runtime):
    """Resolve containers pelas duas labels Compose, nunca por nome aproximado."""

    def containers(self, service: str) -> list[str]:
        prefix = self.config.name + "_"
        own = service.startswith(prefix)
        project = self.config.name if own else self.config.chatwoot_project
        name = service[len(prefix) :] if own else service
        return (
            self.run(
                "ps",
                "-q",
                "--filter",
                f"label=com.docker.compose.project={project}",
                "--filter",
                f"label=com.docker.compose.service={name}",
            )
            .decode()
            .split()
        )


class ComposeLifecycle(Lifecycle):
    """Altera só infraestrutura; backup, contas e recuperação permanecem comuns."""

    def __init__(self, config: Deployment, directory: Path) -> None:
        super().__init__(config, directory.resolve())
        self.runtime = ComposeRuntime(config)

    @property
    def mounts(self) -> Path:
        """Diretório durável privado, necessário aos bind mounts Compose."""
        return self.state.directory / "mounts"

    def compose(self, *args: str) -> bytes:
        """Executa somente o projeto e documento deste manifesto."""
        return self.runtime.run(
            "compose",
            "-p",
            self.config.name,
            "-f",
            str(self.state.directory / "compose.json"),
            *args,
        )

    def check_environment(self) -> None:
        """Confirma Compose, redes bridge e serviços do projeto Chatwoot."""
        r = self.runtime
        r.run("compose", "version")
        endpoint = r.json("context", "inspect", self.config.context)[0]
        if not endpoint["Endpoints"]["docker"]["Host"].startswith("unix://"):
            raise InspectionError("Compose requer contexto local com bind mounts.")
        for name in {self.config.network, self.config.chatwoot_network}:
            net = r.json("network", "inspect", name)[0]
            if net.get("Driver") != "bridge" or net.get("Scope") != "local":
                raise InspectionError("Compose requer redes bridge locais existentes.")
        rails = r.json("inspect", r.container(self.config.chatwoot_service))[0]
        if self.config.chatwoot_network not in rails["NetworkSettings"]["Networks"]:
            raise InspectionError("Rails não está na rede Chatwoot selecionada.")
        host = urlsplit(self.config.chatwoot_url).hostname
        aliases = rails["NetworkSettings"]["Networks"][self.config.chatwoot_network]
        if host not in (aliases.get("Aliases") or []):
            raise InspectionError(
                "URL Chatwoot deve usar alias Rails na rede escolhida."
            )
        r.container(self.config.chatwoot_database_service)

    def check_services(self, identity: str | None) -> None:
        """Inclui containers parados e rede privada na verificação de propriedade."""
        r = self.runtime
        ids = (
            r.run(
                "ps",
                "-aq",
                "--filter",
                f"label=com.docker.compose.project={self.config.name}",
            )
            .decode()
            .split()
        )
        for item in ids:
            labels = r.json("inspect", item)[0]["Config"].get("Labels") or {}
            if not identity or labels.get(OWNER) != identity:
                raise InspectionError(
                    "Projeto Compose preexistente alheio ao manifesto."
                )
        names = r.run("network", "ls", "--format", "{{.Name}}").decode().split()
        private = self.config.name + "_private"
        if private in names:
            labels = r.json("network", "inspect", private)[0].get("Labels") or {}
            if not identity or labels.get(OWNER) != identity:
                raise InspectionError("Rede privada preexistente alheia ao manifesto.")

    def resources(self) -> None:
        """Materializa só infraestrutura em mounts privados; nunca token Chatwoot."""
        if not (self.state.directory / "infrastructure.fernet").exists():
            self.state.save_vault(
                {
                    "password": secrets.token_hex(32),
                    "encryption_key": Fernet.generate_key().decode(),
                }
            )
        vault = self.state.vault()
        self.mounts.mkdir(mode=0o700, exist_ok=True)
        self.mounts.chmod(0o700)
        values = {
            "database_password": vault["password"],
            "encryption_key": vault["encryption_key"],
            "database_url": (
                f"postgresql://kanban:{vault['password']}@"
                f"{self.config.name}_postgres:5432/kanban"
            ),
            "entrypoint.sh": ENTRYPOINT.replace(
                'exec "$@"', 'exec python /run/config/drop.py "$@"'
            ),
            "drop.py": DROP,
            "nginx.conf": nginx(self.config),
        }
        for name, value in values.items():
            write_private(self.mounts / name, value.encode())

    def deploy(self, image: str, running: bool = False) -> None:
        """Aplica documento próprio, iniciando somente banco antes da migração."""
        rendered = document(
            self.config, self.state.data["identity"], image, self.mounts
        )
        write_private(
            self.state.directory / "compose.json", json.dumps(rendered).encode()
        )
        targets = ["postgres", "api", "worker", "nginx"] if running else ["postgres"]
        self.compose("up", "-d", "--no-deps", *targets)

    def stop_app(self) -> None:
        """Para containers antes do backup, inclusive durante recuperação de falha."""
        if (self.state.directory / "compose.json").exists():
            self.compose("stop", "-t", "30", "api", "worker", "migrate", "nginx")

    def migrate_and_start_api(self) -> None:
        """run --rm cria um job novo e seu exit code bloqueia falhas de migração."""
        self.compose("run", "--rm", "--no-deps", "-T", "migrate")
        self.compose("up", "-d", "--no-deps", "api", "nginx")

    def start_worker(self) -> None:
        """Inicia worker depois de cifrar o token no banco."""
        self.compose("up", "-d", "--no-deps", "worker")

    def check_worker(self) -> None:
        """Exige container ativo; heartbeat sozinho não comprova execução."""
        self.runtime.container(self.config.name + "_worker")

    def status(self) -> dict:
        """Inclui a rota real Nginx até o Chatwoot e até os arquivos Kanban."""
        report = super().status()
        try:
            proxy = self.runtime.container(self.config.name + "_nginx")
            for path in ("/api", "/kanban/static/loader.js"):
                self.runtime.run(
                    "exec",
                    proxy,
                    "wget",
                    "-q",
                    "-O",
                    "/dev/null",
                    "http://127.0.0.1" + path,
                )
            report["proxy"] = "ok"
        except InspectionError:
            report.update(healthy=False, proxy="unavailable")
        return report

    def remove_services(self) -> None:
        """Remove projeto próprio sem -v; exclui mounts após desmontagem."""
        if (self.state.directory / "compose.json").exists():
            self.compose("down", "--timeout", "30")
        if self.mounts.exists():
            for name in (
                "database_password",
                "database_url",
                "encryption_key",
                "entrypoint.sh",
                "drop.py",
                "nginx.conf",
            ):
                (self.mounts / name).unlink(missing_ok=True)
            if not any(self.mounts.iterdir()):
                self.mounts.rmdir()
