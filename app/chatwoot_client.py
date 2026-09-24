import httpx

from app.config import settings
from app.security import decrypt


class Chatwoot:
    def __init__(self, account, token):
        self.account = account
        self.client = httpx.AsyncClient(
            base_url=f"{settings.chatwoot_base_url}/api/v1/accounts/{account}",
            headers={"api_access_token": token},
            timeout=20,
        )

    async def __aenter__(self):
        return self

    async def __aexit__(self, *_):
        await self.client.aclose()

    async def request(self, method, path, **kwargs):
        response = await self.client.request(method, path, **kwargs)
        response.raise_for_status()
        return response.json() if response.content else {}

    @classmethod
    async def for_account(cls, conn, account):
        token = await conn.fetchval(
            "SELECT token_cipher FROM kb_accounts WHERE account_id=$1", account
        )
        if not token:
            raise ValueError("Conta ainda não ativada")
        return cls(account, decrypt(token))


def failure(exc: Exception, attempts: int = 0) -> tuple[str, int]:
    """Retorna diagnóstico sem corpo/credenciais e atraso limitado para retentativa."""
    delay = min(300, 2 ** min(attempts + 1, 8))
    if isinstance(exc, httpx.HTTPStatusError):
        status = exc.response.status_code
        if status == 429:
            from datetime import UTC, datetime
            from email.utils import parsedate_to_datetime

            raw = exc.response.headers.get("Retry-After", "")
            try:
                delay = int(raw)
            except ValueError:
                try:
                    delay = int(
                        (parsedate_to_datetime(raw) - datetime.now(UTC)).total_seconds()
                    )
                except (ValueError, TypeError, OverflowError):
                    delay = 30
            return "Chatwoot limitou requisições (429)", max(1, min(delay, 3600))
        if status in (401, 403):
            return "Credencial sem autorização; atualize o token da conta", 300
        if status == 404:
            return "Recurso não encontrado no Chatwoot (404)", 300
        return f"Chatwoot indisponível (HTTP {status})", delay
    from app.provisioning.attributes import AttributeConflictError

    if isinstance(exc, AttributeConflictError):
        return str(exc), 300
    return type(exc).__name__, delay
