from __future__ import annotations

import logging
from contextlib import asynccontextmanager

from fastapi import FastAPI

from config.settings import settings
from db.pool import close_pool, get_pool, init_pool
from services.http_client import close_http_clients, init_http_clients
from services.storage import close_storage, init_storage

logger = logging.getLogger(__name__)


@asynccontextmanager
async def lifespan(app: FastAPI):
    logger.info("Starting media-service (env=%s)", settings.app_env)
    await init_pool()
    init_http_clients()
    init_storage()
    logger.info("All clients initialized")
    yield
    await close_http_clients()
    await close_pool()
    close_storage()
    logger.info("All clients closed")


app = FastAPI(
    title="Agora Media Service",
    version="0.1.0",
    lifespan=lifespan,
)

from api.routes import router
app.include_router(router, prefix="/media")


@app.get("/health")
async def health() -> dict:
    db_status = "connected"
    storage_status = "connected"

    try:
        pool = get_pool()
        await pool.fetchval("SELECT 1")
    except Exception:
        db_status = "error"

    try:
        from services.storage import _get_client
        if _get_client() is not None:
            pass
    except Exception:
        storage_status = "error"

    return {
        "status": "ok",
        "database": db_status,
        "storage": storage_status,
    }


if __name__ == "__main__":
    import uvicorn
    uvicorn.run(
        "main:app",
        host="0.0.0.0",
        port=settings.app_port,
        reload=settings.app_env == "development",
    )
