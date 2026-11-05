from contextlib import asynccontextmanager
from pathlib import Path

import truststore
from fastapi import FastAPI
from fastapi.responses import FileResponse
from fastapi.staticfiles import StaticFiles

from . import __version__
from .api import router
from .config import get_settings
from .db import SessionLocal, dispose_db, init_db
from .security import RequestContextMiddleware
from .services.agents import seed_agents

# Use the operating system CA store while keeping certificate verification enabled.
truststore.inject_into_ssl()

STATIC_ROOT = Path(__file__).parent / "static"


@asynccontextmanager
async def lifespan(app: FastAPI):
    settings = get_settings()
    if settings.production and not settings.api_key:
        raise RuntimeError("TITAN_API_KEY is required in production")
    await init_db()
    async with SessionLocal() as db:
        await seed_agents(db)
    yield
    await dispose_db()


app = FastAPI(
    title="TITAN OMEGA INFINITY V18",
    summary="Verified AI research, agent, skill, memory and development control plane",
    version=__version__,
    lifespan=lifespan,
)
app.add_middleware(RequestContextMiddleware)
app.include_router(router)
app.mount("/static", StaticFiles(directory=STATIC_ROOT), name="static")


@app.get("/", include_in_schema=False)
async def index():
    return FileResponse(STATIC_ROOT / "index.html")


@app.get("/health", tags=["system"])
async def health():
    # Liveness only; capability truth is available at authenticated /api/v1/system.
    return {"status": "ok", "version": __version__}
