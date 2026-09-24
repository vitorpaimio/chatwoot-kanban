"""Manifesto persistente, exclusão mútua e cofre cifrado do instalador."""

import fcntl
import json
import os
from pathlib import Path

from cryptography.fernet import Fernet

from installer.swarm import InspectionError


def write_private(path: Path, data: bytes) -> None:
    """Substitui arquivo de estado sem janela de permissões abertas."""
    temporary = path.with_suffix(path.suffix + ".new")
    fd = os.open(
        temporary, os.O_WRONLY | os.O_CREAT | os.O_TRUNC | os.O_NOFOLLOW, 0o600
    )
    try:
        with os.fdopen(fd, "wb") as stream:
            os.fchmod(stream.fileno(), 0o600)
            stream.write(data)
            stream.flush()
            os.fsync(stream.fileno())
        temporary.replace(path)
    finally:
        temporary.unlink(missing_ok=True)


class State:
    """Só operações mutáveis criam estado local; plano/status são somente leitura."""

    def __init__(self, directory: Path) -> None:
        self.directory = directory
        self.manifest = directory / "manifest.json"
        self.data = (
            json.loads(self.manifest.read_text()) if self.manifest.exists() else {}
        )

    def lock(self) -> None:
        """Recusa execução concorrente no mesmo diretório."""
        self.directory.mkdir(parents=True, exist_ok=True, mode=0o700)
        self.directory.chmod(0o700)
        fd = os.open(
            self.directory / "operation.lock",
            os.O_RDWR | os.O_CREAT | os.O_NOFOLLOW,
            0o600,
        )
        os.fchmod(fd, 0o600)
        self._lock = os.fdopen(fd, "a+b")
        try:
            fcntl.flock(self._lock, fcntl.LOCK_EX | fcntl.LOCK_NB)
        except BlockingIOError:
            self._lock.close()
            raise InspectionError("Já existe uma operação neste diretório.")
        self.data = (
            json.loads(self.manifest.read_text()) if self.manifest.exists() else {}
        )

    def close(self) -> None:
        """Libera a trava, inclusive após falhas."""
        if hasattr(self, "_lock"):
            self._lock.close()

    def save(self, **changes: object) -> None:
        """Persiste somente metadados públicos e recibos sem credenciais."""
        self.data.update(changes)
        write_private(self.manifest, json.dumps(self.data, indent=2).encode())

    def cipher(self, create: bool = False) -> Fernet:
        """Carrega chave durável de backup; nunca a imprime."""
        path = self.directory / "recovery.key"
        if not path.exists() and create:
            write_private(path, Fernet.generate_key())
        return Fernet(path.read_bytes())

    def vault(self) -> dict:
        """Recupera credenciais de infraestrutura cifradas, nunca token Chatwoot."""
        path = self.directory / "infrastructure.fernet"
        return json.loads(self.cipher().decrypt(path.read_bytes()))

    def save_vault(self, value: dict) -> None:
        """Grava infraestrutura cifrada sem cópia em claro no filesystem."""
        write_private(
            self.directory / "infrastructure.fernet",
            self.cipher(create=True).encrypt(json.dumps(value).encode()),
        )
