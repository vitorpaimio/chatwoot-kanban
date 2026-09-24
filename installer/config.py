"""Contrato sem credenciais para uma instalação Swarm."""

import ipaddress
import re
from typing import Literal
from urllib.parse import urlsplit

from pydantic import BaseModel, ConfigDict, Field, model_validator


class Deployment(BaseModel):
    """Identifica recursos existentes e os recursos próprios a criar."""

    model_config = ConfigDict(extra="forbid")
    adapter: Literal["swarm", "compose"] = "swarm"
    chatwoot_project: str | None = None
    listen_host: str = "127.0.0.1"
    listen_port: int = Field(default=18080, ge=1, le=65535)
    name: str = Field(pattern=r"^[a-z][a-z0-9-]{2,35}$")
    context: str
    accounts: list[int] = Field(min_length=1)
    image: str
    public_url: str
    chatwoot_url: str
    chatwoot_service: str
    chatwoot_database_service: str
    chatwoot_database: str = "chatwoot"
    chatwoot_database_user: str = "postgres"
    chatwoot_network: str
    network: str = "network_public"
    rails_wrapper: list[str] = Field(default_factory=list)
    entrypoint: str = "websecure"
    tls: bool = True
    allow_local_image: bool = False

    @property
    def callback_url(self) -> str:
        """Usa origem pública no Swarm; preserva o contrato local Compose."""
        return (
            self.public_url.rstrip("/")
            if self.adapter == "swarm"
            else f"http://{self.name}_api:8000"
        )

    @model_validator(mode="after")
    def validate_contract(self) -> "Deployment":
        """Rejeita destinos ambíguos e parâmetros que poderiam conter segredos."""
        for value in (
            self.context,
            self.chatwoot_service,
            self.chatwoot_database_service,
            self.chatwoot_database,
            self.chatwoot_database_user,
            self.chatwoot_network,
            self.network,
            self.entrypoint,
        ):
            if not re.fullmatch(r"[a-zA-Z0-9][a-zA-Z0-9_.-]{0,127}", value):
                raise ValueError("Identificador inválido")
        for value in (self.public_url, self.chatwoot_url):
            url = urlsplit(value)
            if (
                url.scheme not in ("http", "https")
                or not url.hostname
                or url.username
                or url.password
                or url.query
                or url.fragment
                or url.path not in ("", "/")
                or not re.fullmatch(r"[a-zA-Z0-9._-]+", url.hostname)
            ):
                raise ValueError("URL deve ter somente protocolo, host e porta")
        if any(type(a) is not int or a <= 0 for a in self.accounts):
            raise ValueError("Selecione contas positivas")
        self.accounts = sorted(set(self.accounts))
        if not re.fullmatch(r"[a-zA-Z0-9_./:@-]+", self.image):
            raise ValueError("Imagem inválida")
        if not self.allow_local_image and not re.search(
            r"@sha256:[a-f0-9]{64}$", self.image
        ):
            raise ValueError("Use uma imagem fixada por digest")
        if len(self.rails_wrapper) > 4 or any(
            not re.fullmatch(r"[a-zA-Z0-9_./-]+", v) for v in self.rails_wrapper
        ):
            raise ValueError("Wrapper deve conter apenas executável e caminhos")
        if self.adapter == "compose":
            if not self.chatwoot_project or not re.fullmatch(
                r"[a-z][a-z0-9_-]{1,62}", self.chatwoot_project
            ):
                raise ValueError("Selecione o projeto Compose existente do Chatwoot")
            if self.chatwoot_project == self.name:
                raise ValueError("Kanban exige projeto separado do Chatwoot")
            if self.tls or urlsplit(self.public_url).scheme != "http":
                raise ValueError(
                    "Compose certifica HTTP; TLS externo exige validação própria"
                )
            ipaddress.IPv4Address(self.listen_host)
            if (urlsplit(self.public_url).port or 80) != self.listen_port:
                raise ValueError("Porta pública deve corresponder à porta do Nginx")
        return self
