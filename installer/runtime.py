"""Transporte administrativo sem eco de respostas sensíveis."""

import json
import subprocess
import time
from pathlib import Path

from installer.config import Deployment
from installer.swarm import InspectionError


class Runtime:
    """Executa comandos somente no contexto explicitamente selecionado."""

    def __init__(self, config: Deployment) -> None:
        self.config = config

    def run(self, *args: str, data: bytes | None = None) -> bytes:
        """Transporta segredos em pipes; erros públicos não incluem stdout/stderr."""
        try:
            result = subprocess.run(
                ["docker", "--context", self.config.context, *args],
                input=data,
                capture_output=True,
                check=True,
                timeout=180,
            )
            return result.stdout
        except (OSError, subprocess.SubprocessError):
            raise InspectionError(f"Falha Docker na operação {args[0]}; saída omitida.")

    def json(self, *args: str) -> dict | list:
        """Decodifica resposta de inspeção."""
        return json.loads(self.run(*args))

    def container(self, service: str) -> str:
        """Exige uma única tarefa local executável; não adivinha nó remoto."""
        ids = self.containers(service)
        if len(ids) != 1:
            raise InspectionError(f"Serviço {service} exige uma réplica local ativa.")
        return ids[0]

    def containers(self, service: str) -> list[str]:
        """Lista réplicas locais em execução."""
        return (
            self.run(
                "ps", "-q", "--filter", f"label=com.docker.swarm.service.name={service}"
            )
            .decode()
            .split()
        )

    def rails(self, request: dict) -> dict:
        """Executa o adaptador com parâmetros e credenciais somente em memória."""
        script = Path(__file__).with_name("resources.rb").read_text()
        # JSON embutido como string Ruby, sem interpolação de expressões remotas.
        prefix = (
            "require 'json'\nrequest = JSON.parse("
            + json.dumps(json.dumps(request), ensure_ascii=True)
            + ")\n"
        )
        result = self.run(
            "exec",
            "-i",
            self.container(self.config.chatwoot_service),
            *self.config.rails_wrapper,
            "bundle",
            "exec",
            "rails",
            "runner",
            "-",
            data=(prefix + script).encode(),
        ).decode()
        lines = [
            line[14:]
            for line in result.splitlines()
            if line.startswith("KANBAN_RESULT=")
        ]
        if len(lines) != 1:
            raise InspectionError("Adaptador Rails não retornou um recibo único.")
        return json.loads(lines[0])

    def wait_container(self, service: str, seconds: int = 120) -> str:
        """Aguarda a tarefa em execução com prazo finito."""
        deadline = time.monotonic() + seconds
        while time.monotonic() < deadline:
            try:
                return self.container(service)
            except InspectionError:
                time.sleep(2)
        raise InspectionError(f"Prazo excedido ao iniciar {service}.")

    def wait_job(self, service: str, previous: set[str] | None = None) -> None:
        """Confirma término do job de migração, não apenas criação da tarefa."""
        deadline = time.monotonic() + 120
        while time.monotonic() < deadline:
            ids = self.run("service", "ps", "-q", service).decode().split()
            ids = [task for task in ids if task not in (previous or set())]
            if ids:
                state = self.json("inspect", ids[0])[0]["Status"]
                if state["State"] == "complete":
                    return
                if state["State"] in ("failed", "rejected"):
                    raise InspectionError(
                        "Migração falhou; restaure o backup antes de regredir esquema."
                    )
            time.sleep(2)
        raise InspectionError("Migração não concluiu no prazo.")
