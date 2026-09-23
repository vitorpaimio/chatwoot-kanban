"""Ativa contas locais usando a sessão administrativa, sem persistir a sessão."""

import asyncio
import getpass
import os

import httpx


async def main():
    email = os.environ.get("CHATWOOT_LOGIN_EMAIL") or input("E-mail do administrador: ")
    password = os.environ.get("CHATWOOT_LOGIN_PASSWORD") or getpass.getpass("Senha: ")
    async with httpx.AsyncClient(
        base_url="http://localhost:3000", timeout=30
    ) as client:
        login = await client.post(
            "/auth/sign_in", json={"email": email, "password": password}
        )
        login.raise_for_status()
        headers = {key: login.headers[key] for key in ("access-token", "client", "uid")}
        profile = await client.get("/api/v1/profile", headers=headers)
        profile.raise_for_status()
        profile = profile.json()
        for account in profile["accounts"]:
            if account["role"] != "administrator":
                continue
            response = await client.post(
                "/kanban/activate",
                params={"account": account["id"]},
                headers=headers,
                json={"token": profile["access_token"]},
            )
            response.raise_for_status()
            print(f"Conta {account['id']}: ativação agendada.")
        await client.delete("/auth/sign_out", headers=headers)


asyncio.run(main())
