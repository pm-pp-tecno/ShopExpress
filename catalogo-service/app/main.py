import logging
from contextlib import asynccontextmanager

from fastapi import FastAPI
from motor.motor_asyncio import AsyncIOMotorClient
from neo4j import AsyncGraphDatabase

from app.config import settings
from app.repository import GrafoRepository, InventarioRepository
from app.router import router
from app.service import CatalogoService

logging.basicConfig(level=logging.INFO)


@asynccontextmanager
async def lifespan(app: FastAPI):
    mongo = AsyncIOMotorClient(settings.mongo_uri, serverSelectionTimeoutMS=5000)
    driver = AsyncGraphDatabase.driver(
        settings.neo4j_uri,
        auth=(settings.neo4j_user, settings.neo4j_password),
    )
    inventario = InventarioRepository(mongo)
    grafo = GrafoRepository(driver)
    await inventario.ensure_indexes()
    await grafo.ensure_constraints()
    app.state.mongo = mongo
    app.state.driver = driver
    app.state.grafo = grafo
    app.state.service = CatalogoService(inventario, grafo)
    yield
    await driver.close()
    mongo.close()


app = FastAPI(title="Catálogo e Inventario", lifespan=lifespan)
app.include_router(router)


@app.get("/health")
async def health():
    await app.state.mongo.admin.command("ping")
    await app.state.grafo.ping()
    return {"status": "ok"}
