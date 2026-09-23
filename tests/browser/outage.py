"""Teste local explícito: interrompe Rails por 60s e reinicia worker."""

import asyncio
import os
import subprocess
import time

import httpx

from app.database import close_pool, connection, init_pool

SOCKET = "/Users/paim/chatwoot-kanban/.overmind-kanban.sock"


def control(action, process):
    subprocess.run(
        ["/opt/homebrew/bin/overmind", action, "-s", SOCKET, process], check=True
    )


async def main():
    email = os.environ["CHATWOOT_LOGIN_EMAIL"]
    password = os.environ["CHATWOOT_LOGIN_PASSWORD"]
    await init_pool()
    async with httpx.AsyncClient(
        base_url="http://localhost:3000", timeout=10
    ) as client:
        login = await client.post(
            "/auth/sign_in",
            json={
                "email": email,
                "password": password,
            },
        )
        login.raise_for_status()
        headers = {k: login.headers[k] for k in ("access-token", "client", "uid")}
        client.headers.update(headers)

        async def api(path, method="GET", body=None):
            r = await client.request(
                method, "/kanban" + path, params={"account": 1}, json=body
            )
            r.raise_for_status()
            return r.json()

        data = await api("/board")
        card = next(
            c for c in data["cards"] if c["name"].startswith("Cliente de teste Kanban")
        )
        contact = card["contact_id"]
        control("stop", "worker")
        await api(
            f"/contacts/{contact}/task",
            "PUT",
            {
                "descricao": "Teste de indisponibilidade — pendente",
                "vencimento": "2026-09-24",
                "version": card["task_version"],
            },
        )
        control("stop", "rails")
        control("restart", "worker")
        started = time.monotonic()
        try:
            for seconds in range(60):
                await asyncio.sleep(1)
                if seconds in (19, 39, 59):
                    async with connection() as conn:
                        row = await conn.fetchrow(
                            """SELECT status,attempts FROM kb_sync
                        WHERE account_id=1 AND contact_id=$1""",
                            contact,
                        )
                    print(f"Rails indisponível {seconds + 1}s: {dict(row)}", flush=True)
            assert time.monotonic() - started >= 60
            async with connection() as conn:
                assert (
                    await conn.fetchval(
                        """SELECT status FROM kb_sync
                        WHERE account_id=1 AND contact_id=$1""",
                        contact,
                    )
                    == "failed"
                )
            control("stop", "worker")
        finally:
            control("restart", "rails")
        for _ in range(45):
            try:
                data = await api("/board")
                break
            except httpx.HTTPError:
                await asyncio.sleep(1)
        else:
            raise RuntimeError("Rails não retomou")
        card = next(c for c in data["cards"] if c["contact_id"] == contact)
        await api(
            f"/contacts/{contact}/task",
            "PUT",
            {
                "descricao": "Sincronização recuperada após reinício",
                "vencimento": "2026-09-24",
                "version": card["task_version"],
            },
        )
        stages = [s for s in data["stages"] if s["funnel_id"] == card["funnel_id"]]
        await api(
            f"/cards/{card['id']}",
            "PATCH",
            {"version": card["version"], "stage_id": stages[0]["id"]},
        )
        await api(
            f"/cards/{card['id']}",
            "PATCH",
            {"version": card["version"] + 1, "stage_id": stages[1]["id"]},
        )
        control("restart", "worker")
        for _ in range(45):
            async with connection() as conn:
                row = await conn.fetchrow(
                    "SELECT * FROM kb_sync WHERE account_id=1 AND contact_id=$1",
                    contact,
                )
            if row["status"] == "synced":
                assert row["version"] == row["synced_version"]
                assert (
                    row["projection"]["kanban_tarefa"]
                    == "Sincronização recuperada após reinício"
                )
                assert row["projection"]["kanban_etapa"].endswith(
                    " / " + stages[1]["name"]
                )
                print(
                    "OK: fila recuperada, estado final sincronizado "
                    "e movimentos antigos não restaurados.",
                    flush=True,
                )
                break
            await asyncio.sleep(1)
        else:
            raise RuntimeError("Sincronização não retomou")
        await client.delete("/auth/sign_out")
    await close_pool()


if __name__ == "__main__":
    if not all(
        os.environ.get(key)
        for key in ("CHATWOOT_LOGIN_EMAIL", "CHATWOOT_LOGIN_PASSWORD")
    ):
        raise SystemExit(
            "Configure CHATWOOT_LOGIN_EMAIL e CHATWOOT_LOGIN_PASSWORD. "
            "Use somente uma conta local de testes."
        )
    try:
        asyncio.run(main())
    finally:
        control("restart", "rails")
        control("restart", "worker")
