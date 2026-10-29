import asyncio
import logging
from contextlib import asynccontextmanager

import httpx
from fastapi import FastAPI
from motor.motor_asyncio import AsyncIOMotorClient

from app.clientes import CatalogoCliente, UsuariosCliente
from app.config import settings
from app.repository import PedidoRepository
from app.router import router
from app.service import PedidoService

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger("pedidos")


@asynccontextmanager
async def lifespan(app: FastAPI):
    mongo = AsyncIOMotorClient(settings.mongo_uri, serverSelectionTimeoutMS=5000)
    repo = PedidoRepository(mongo)
    await repo.ensure_indexes()
    http = httpx.AsyncClient(timeout=10.0)
    service = PedidoService(
        repo,
        UsuariosCliente(http, settings.usuarios_url),
        CatalogoCliente(http, settings.catalogo_url),
    )
    app.state.mongo = mongo
    app.state.http = http
    app.state.service = service
    for intento in range(5):
        try:
            await service.reanudar()
            break
        except Exception:
            logger.exception("Reanudación al arrancar, intento %s", intento + 1)
            await asyncio.sleep(2)
    yield
    await http.aclose()
    mongo.close()


app = FastAPI(title="Pedidos y Pagos", lifespan=lifespan)
app.include_router(router)


@app.get("/health")
async def health():
    await app.state.mongo.admin.command("ping")
    return {"status": "ok"}
