import logging
from contextlib import asynccontextmanager

import httpx
from fastapi import FastAPI
from motor.motor_asyncio import AsyncIOMotorClient

from app.config import settings
from app.repository import UsuarioRepository
from app.router import router
from app.service import UsuarioService

logging.basicConfig(level=logging.INFO)


@asynccontextmanager
async def lifespan(app: FastAPI):
    mongo = AsyncIOMotorClient(settings.mongo_uri, serverSelectionTimeoutMS=5000)
    repo = UsuarioRepository(mongo)
    await repo.ensure_indexes()
    http = httpx.AsyncClient(timeout=10.0)
    app.state.mongo = mongo
    app.state.http = http
    app.state.service = UsuarioService(repo, http, settings.pedidos_url)
    yield
    await http.aclose()
    mongo.close()


app = FastAPI(title="Usuarios", lifespan=lifespan)
app.include_router(router)


@app.get("/health")
async def health():
    await app.state.mongo.admin.command("ping")
    return {"status": "ok"}
