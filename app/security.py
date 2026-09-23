import json
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
    try:
        async with httpx.AsyncClient(timeout=10) as client:
            response = await client.get(
                settings.chatwoot_base_url + "/api/v1/profile", headers=credentials
            )
        if response.status_code in (401, 403):
            raise HTTPException(401, "Sessão expirada")
        response.raise_for_status()
        profile = response.json()
    except httpx.HTTPError:
        raise HTTPException(
            503, "Não foi possível validar a sessão no Chatwoot"
        ) from None
    try:
        account = int(request.query_params["account"])
    except (KeyError, ValueError):
        raise HTTPException(400, "Informe a conta") from None
    membership = next(
        (a for a in profile.get("accounts", []) if a["id"] == account), None
    )
    if not membership or membership.get("status") != "active":
        raise HTTPException(403, "Conta não autorizada")
    return {
        "id": profile["id"],
        "name": profile["name"],
        "account": account,
        "role": membership["role"],
    }


def administrator(user):
    if user["role"] != "administrator":
        raise HTTPException(403, "Apenas administradores podem realizar esta operação")


get_actor = identity
