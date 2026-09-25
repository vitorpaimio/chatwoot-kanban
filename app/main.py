import re
from contextlib import asynccontextmanager
from pathlib import Path

import asyncpg
from fastapi import FastAPI
from fastapi.responses import FileResponse, HTMLResponse, JSONResponse
from fastapi.staticfiles import StaticFiles

from app.database import close_pool, init_pool
from app.events import hub
from app.health import health_status
from app.routers.metrics import router as metrics_router
from app.routers.pages import router as pages_router
from app.routers.provisioning import router as provisioning_router
from app.routers.workspace import router
from app.security import cipher

ROOT = Path(__file__).parent
ASSET = re.compile(r'"/kanban/static/([\w./-]+)"')


def page(name: str) -> HTMLResponse:
    """Serve a página com a versão de cada arquivo estático na URL.

    A versão muda quando o arquivo muda, o que permite ao navegador guardar
    JS, CSS e Chart.js sem revalidar a cada abertura do quadro.
    """

    def stamp(match: re.Match) -> str:
        asset = match.group(1)
        stat = (ROOT / "static" / asset).stat()
        return f'"/kanban/static/{asset}?v={stat.st_mtime_ns:x}{stat.st_size:x}"'

    html = (ROOT / "templates" / name).read_text()
    return HTMLResponse(ASSET.sub(stamp, html))


@asynccontextmanager
async def lifespan(_app):
    cipher()
    await init_pool()
    try:
        yield
    finally:
        await hub.close()
        await close_pool()


app = FastAPI(
    title="Kanban integrado ao Chatwoot",
    lifespan=lifespan,
    docs_url=None,
    redoc_url=None,
    openapi_url=None,
)
app.include_router(router)
app.include_router(provisioning_router)
app.include_router(metrics_router)
app.include_router(pages_router)
app.mount("/kanban/static", StaticFiles(directory=ROOT / "static"), name="static")


@app.middleware("http")
async def security_headers(request, call_next):
    response = await call_next(request)
    response.headers["X-Content-Type-Options"] = "nosniff"
    response.headers["Referrer-Policy"] = "same-origin"
    path = request.url.path
    if path.startswith("/kanban/static/") and request.query_params.get("v"):
        cache = "public, max-age=31536000, immutable"
    elif path.startswith("/kanban/static/") or path == "/kanban/loader.js":
        cache = "no-cache"
    else:
        cache = "no-store"
    response.headers["Cache-Control"] = cache
    response.headers["Content-Security-Policy"] = (
        "default-src 'self'; frame-ancestors 'self'; style-src 'self' '"
        "unsafe-inline'; img-src 'self' data: https:; connect-src 'self"
        "'; script-src 'self'"
    )
    return response


@app.get("/kanban/")
@app.get("/kanban")
async def interface():
    return page("kanban.html")


@app.get("/kanban/metricas")
async def metrics_interface():
    return page("metricas.html")


@app.get("/kanban/tarefas")
async def tasks_interface():
    return page("tarefas.html")


@app.get("/kanban/configuracoes")
async def settings_interface():
    return page("configuracoes.html")


@app.get("/kanban/loader.js")
async def loader():
    return FileResponse(ROOT / "static" / "loader.js", media_type="text/javascript")


@app.get("/health")
async def health():
    result = await health_status()
    return JSONResponse(result, status_code=200 if result["status"] == "ok" else 503)


@app.get("/health/worker")
async def worker_health():
    result = await health_status()
    healthy = result.get("worker") == "ok"
    return JSONResponse({"status": "ok" if healthy else "unavailable"},
                        status_code=200 if healthy else 503)


@app.exception_handler(asyncpg.UniqueViolationError)
async def duplicate_record(_request, _error):
    return JSONResponse(
        status_code=409,
        content={
            "detail": "Já existe um registro com esses dados nesta conta ou funil."
        },
    )
