import asyncio
import logging
import uuid

from pymongo.errors import DuplicateKeyError

from app.chain import Contexto, construir_cadena
from app.clientes import CatalogoCliente, SagaPendiente, UsuariosCliente
from app.models import PedidoIn
from app.repository import PedidoRepository
from app.saga import OrquestadorSaga

logger = logging.getLogger("pedidos")


def nuevo_id(prefijo: str) -> str:
    return f"{prefijo}_{uuid.uuid4().hex[:8]}"


class PedidoService:
    def __init__(self, repo: PedidoRepository, usuarios: UsuariosCliente, catalogo: CatalogoCliente):
        self.repo = repo
        self.usuarios = usuarios
        self.catalogo = catalogo
        self.saga = OrquestadorSaga(repo, catalogo)
        self.cadena = construir_cadena()
        self._locks: dict[str, asyncio.Lock] = {}

    def _lock(self, clave: str) -> asyncio.Lock:
        if clave not in self._locks:
            self._locks[clave] = asyncio.Lock()
        return self._locks[clave]

    async def crear(self, datos: PedidoIn, clave: str | None, pausar: str | None):
        idempotency_key = clave or datos.idempotency_key or nuevo_id("idem")
        async with self._lock(idempotency_key):
            existente = await self.repo.por_clave(idempotency_key)
            if existente:
                return await self.saga.avanzar(existente, pausar=pausar)

            ctx = Contexto(datos, self.usuarios, self.catalogo)
            await self.cadena.handle(ctx)
            pedido_id = nuevo_id("ord")
            doc = {
                "_id": pedido_id,
                "pedido_id": pedido_id,
                "usuario_id": datos.usuario_id,
                "estado": "PENDIENTE",
                "items": ctx.items,
                "total": str(ctx.total),
                "pago": {
                    "metodo": datos.pago.metodo,
                    "resultado": datos.pago.resultado,
                    "estado_pago": None,
                    "transaccion_id": None,
                },
                "idempotency_key": idempotency_key,
                "saga": {"paso": "CREADO", "reservas": [], "compensacion": None},
            }
            try:
                await self.repo.insertar(doc)
            except DuplicateKeyError:
                existente = await self.repo.por_clave(idempotency_key)
                return await self.saga.avanzar(existente, pausar=pausar)
            return await self.saga.avanzar(doc, pausar=pausar)

    async def obtener(self, pedido_id: str):
        return await self.repo.obtener(pedido_id)

    async def por_usuario(self, usuario_id: str):
        return await self.repo.por_usuario(usuario_id)

    async def reanudar(self) -> list[str]:
        ids = []
        for doc in await self.repo.pendientes():
            try:
                async with self._lock(doc["idempotency_key"]):
                    fresco = await self.repo.obtener(doc["pedido_id"])
                    if fresco and fresco["estado"] == "PENDIENTE":
                        await self.saga.avanzar(fresco, pausar=None)
                ids.append(doc["pedido_id"])
            except (SagaPendiente, Exception):
                logger.exception("No se pudo reanudar %s", doc["pedido_id"])
        return ids
