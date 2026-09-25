import os
from urllib.parse import urlparse

import httpx
import pytest_asyncio
from cryptography.fernet import Fernet

os.environ["DATABASE_URL"] = os.environ.get(
    "TEST_DATABASE_URL", "postgresql://paim@localhost:5432/kanban_test"
)
if not urlparse(os.environ["DATABASE_URL"]).path.endswith("_test"):
    raise RuntimeError("Os testes exigem banco exclusivo com sufixo _test")

os.environ["ENCRYPTION_KEY"] = Fernet.generate_key().decode()

from app import database, security
from app.main import app
from app.security import encrypt, identity


@pytest_asyncio.fixture(autouse=True)
def fresh_sessions():
    security._profile_cache.clear()
    yield
    security._profile_cache.clear()


@pytest_asyncio.fixture
async def db():
    await database.init_pool()
    async with database.connection() as conn:
        await conn.execute("TRUNCATE kb_accounts CASCADE")
        for account in (1, 2):
            await conn.execute(
                """
        INSERT INTO
        kb_accounts(account_id,token_cipher,webhook_cipher,activation_status)
        VALUES($1,$2,$3, 'ready' )
        """,
                account,
                encrypt("service-token"),
                encrypt("webhook-secret"),
            )
            fid = await conn.fetchval(
                """
        INSERT INTO kb_funnels(account_id,name,is_primary) VALUES($1,
        'Principal' ,true) RETURNING id
        """,
                account,
            )
            for i, name in enumerate(("Novo", "Ganho", "Perdido")):
                await conn.execute(
                    """
        INSERT INTO kb_stages(account_id,funnel_id,name,kind,position)
        VALUES($1,$2,$3,$4,$5)
        """,
                    account,
                    fid,
                    name,
                    ("open", "won", "lost")[i],
                    i * 1024 + 1024,
                )
            await conn.execute(
                """
        INSERT INTO kb_contacts(account_id,contact_id,name) VALUES($1,10,
        'Maria' )
        """,
                account,
            )
            await conn.execute(
                """
        INSERT INTO kb_cards(account_id,contact_id,funnel_id,stage_id) SELECT
        $1,10,$2,id FROM kb_stages WHERE account_id=$1 AND funnel_id=$2 ORDER
        BY position LIMIT 1
        """,
                account,
                fid,
            )
    yield database
    app.dependency_overrides.clear()
    await database.close_pool()


@pytest_asyncio.fixture
async def client(db):
    async def admin():
        return {"account": 1, "id": 3, "name": "Administrador", "role": "administrator"}

    app.dependency_overrides[identity] = admin
    async with httpx.AsyncClient(
        transport=httpx.ASGITransport(app=app), base_url="http://localhost:3000"
    ) as client:
        yield client
