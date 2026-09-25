import hashlib
import json
import time
from urllib.parse import unquote

import httpx
from cryptography.fernet import Fernet
from fastapi import HTTPException, Request

from app.config import settings


def cipher():
    if not settings.encryption_key:
        raise RuntimeError("ENCRYPTION_KEY não configurada")
    return Fernet(settings.encryption_key.encode())


def encrypt(value):
    return cipher().encrypt(value.encode()).decode()


def decrypt(value):
    return cipher().decrypt(value.encode()).decode()


INBOX_TTL = 60
_inbox_cache = {}


async def allowed_inboxes(account: int, actor: int, credentials: dict) -> list[int]:
    """Consulta com sessão humana; cache nunca prolonga o prazo numa falha."""
    fingerprint = hashlib.sha256(
        json.dumps(credentials, sort_keys=True).encode()
    ).digest()
    key = (account, actor, fingerprint)
    now = time.monotonic()
    for old in list(_inbox_cache):
        if _inbox_cache[old][0] <= now:
            del _inbox_cache[old]
    cached = _inbox_cache.get(key)
    if cached:
        return cached[1]
    try:
        async with httpx.AsyncClient(timeout=5) as client:
            response = await client.get(
                f"{settings.chatwoot_base_url}/api/v1/accounts/{account}/inboxes",
                headers=credentials,
            )
        response.raise_for_status()
        payload = response.json()["payload"]
        if not isinstance(payload, list):
            raise ValueError("Resposta inválida")
        ids = [int(row["id"]) for row in payload]
    except (httpx.HTTPError, ValueError, KeyError, TypeError):
        _inbox_cache.pop(key, None)
        raise HTTPException(
            403, "Não foi possível validar as caixas permitidas"
        ) from None
    _inbox_cache[key] = (now + INBOX_TTL, ids)
    return ids


PROFILE_CACHE_LIMIT = 2000
_profile_cache = {}


async def chatwoot_profile(credentials: dict) -> dict:
    """Valida a sessão no Chatwoot com cache curto por credencial.

    Cada chamada ao Kanban revalidava a sessão; o cache evita esse custo no
    carregamento. Só respostas válidas são guardadas, e o prazo limita por quanto
    tempo uma sessão encerrada no Chatwoot ainda é aceita.
    """
    fingerprint = hashlib.sha256(
        json.dumps(credentials, sort_keys=True).encode()
    ).digest()
    now = time.monotonic()
    cached = _profile_cache.get(fingerprint)
    if cached and cached[0] > now:
        return cached[1]
    try:
        async with httpx.AsyncClient(timeout=10) as client:
            response = await client.get(
                settings.chatwoot_base_url + "/api/v1/profile", headers=credentials
            )
        if response.status_code in (401, 403):
            _profile_cache.pop(fingerprint, None)
            raise HTTPException(401, "Sessão expirada")
        response.raise_for_status()
        profile = response.json()
    except httpx.HTTPError:
        raise HTTPException(
            503, "Não foi possível validar a sessão no Chatwoot"
        ) from None
    if settings.session_cache_seconds > 0:
        if len(_profile_cache) >= PROFILE_CACHE_LIMIT:
            for key in [k for k, v in _profile_cache.items() if v[0] <= now]:
                del _profile_cache[key]
            if len(_profile_cache) >= PROFILE_CACHE_LIMIT:
                _profile_cache.clear()
        _profile_cache[fingerprint] = (now + settings.session_cache_seconds, profile)
    return profile


async def identity(request: Request):
    if request.method not in ("GET", "HEAD", "OPTIONS"):
        origin = request.headers.get("origin")
        if origin and origin != settings.public_url:
            raise HTTPException(403, "Origem não autorizada")
        if request.headers.get("sec-fetch-site") == "cross-site":
            raise HTTPException(403, "Origem não autorizada")
    credentials = {
        k: request.headers[k]
        for k in ("access-token", "client", "uid")
        if k in request.headers
    }
    if len(credentials) != 3:
        try:
            raw = json.loads(unquote(request.cookies.get("cw_d_session_info", "")))
            credentials = {k: raw[k] for k in ("access-token", "client", "uid")}
        except (ValueError, KeyError, TypeError):
            raise HTTPException(401, "Entre novamente no Chatwoot") from None
    profile = await chatwoot_profile(credentials)
    try:
        account = int(request.query_params["account"])
    except (KeyError, ValueError):
        raise HTTPException(400, "Informe a conta") from None
    membership = next(
        (a for a in profile.get("accounts", []) if a["id"] == account), None
    )
    if not membership or membership.get("status") != "active":
        raise HTTPException(403, "Conta não autorizada")
    if membership.get("role") not in ("administrator", "agent"):
        raise HTTPException(403, "Papel não autorizado")
    inboxes = (
        []
        if membership["role"] == "administrator"
        else await allowed_inboxes(account, profile["id"], credentials)
    )
    return {
        "inboxes": inboxes,
        "permission_deadline": min(
            (
                v[0]
                for k, v in _inbox_cache.items()
                if k[:2] == (account, profile["id"])
            ),
            default=time.monotonic() + INBOX_TTL,
        ),
        "id": profile["id"],
        "name": profile["name"],
        "account": account,
        "role": membership["role"],
    }


def administrator(user):
    if user["role"] != "administrator":
        raise HTTPException(403, "Apenas administradores podem realizar esta operação")


get_actor = identity
