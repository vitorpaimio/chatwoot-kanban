from contextlib import asynccontextmanager
from pathlib import Path

import asyncpg
from fastapi import FastAPI
from fastapi.responses import FileResponse, JSONResponse
from fastapi.staticfiles import StaticFiles

from app.database import close_pool, init_pool
from app.routers.metrics import router as metrics_router
from app.routers.workspace import router
from app.security import cipher

ROOT = Path(__file__).parent


@asynccontextmanager
async def lifespan(_app):
    cipher()
    await init_pool()
    try:
        yield
    finally:
        await close_pool()


app = FastAPI(
    title="Kanban integrado ao Chatwoot",
    lifespan=lifespan,
    docs_url=None,
    redoc_url=None,
    openapi_url=None,
)
app.include_router(router)
app.include_router(metrics_router)
app.mount("/kanban/static", StaticFiles(directory=ROOT / "static"), name="static")


@app.middleware("http")
async def security_headers(request, call_next):
    response = await call_next(request)
    response.headers["X-Content-Type-Options"] = "nosniff"
    response.headers["Referrer-Policy"] = "same-origin"
    response.headers["Cache-Control"] = "no-store"
    response.headers["Content-Security-Policy"] = (
        "default-src 'self'; frame-ancestors 'self'; style-src 'self' '"
        "unsafe-inline'; img-src 'self' data: https:; connect-src 'self"
        "'; script-src 'self'"
    )
    return response


@app.get("/kanban/")
@app.get("/kanban")
async def interface():
    return FileResponse(ROOT / "templates" / "kanban.html")


@app.get("/kanban/metricas")
async def metrics_interface():
    return FileResponse(ROOT / "templates" / "metricas.html")


@app.get("/kanban/loader.js")
async def loader():
    return FileResponse(ROOT / "static" / "loader.js", media_type="text/javascript")


@app.get("/health")
async def health():
    return {"status": "ok"}


@app.exception_handler(asyncpg.UniqueViolationError)
async def duplicate_record(_request, _error):
    return JSONResponse(
        status_code=409,
        content={
            "detail": "Já existe um registro com esses dados nesta conta ou funil."
        },
    )
