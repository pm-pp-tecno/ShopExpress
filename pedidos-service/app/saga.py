import logging
import uuid

from app.clientes import CatalogoCliente
from app.repository import PedidoRepository

logger = logging.getLogger("pedidos.saga")


def pago_aprobado(pago: dict) -> bool:
    if pago.get("resultado") == "RECHAZADO":
        return False
    if pago.get("metodo") == "TARJETA_RECHAZADA":
        return False
    return True


class OrquestadorSaga:
    """La SAGA vive en este proceso. Cada paso se guarda antes de seguir."""

    def __init__(self, repo: PedidoRepository, catalogo: CatalogoCliente):
        self.repo = repo
        self.catalogo = catalogo

    async def avanzar(self, doc: dict, pausar: str | None = None) -> dict:
        if doc["estado"] != "PENDIENTE":
            return doc
        if doc["saga"].get("compensacion"):
            await self._compensar(doc)
            return doc

        paso = doc["saga"]["paso"]
        if paso in ("CREADO", "RESERVANDO"):
            await self._reservar(doc)
            if doc["estado"] != "PENDIENTE":
                return doc
            if pausar == "RESERVADO":
                return doc

        if doc["saga"]["paso"] == "RESERVADO":
            await self._pagar(doc)
            if doc["estado"] != "PENDIENTE":
                return doc

        if doc["saga"]["paso"] == "PAGO_APROBADO":
            await self._confirmar(doc)
        return doc

    async def _reservar(self, doc: dict):
        doc["saga"]["paso"] = "RESERVANDO"
        await self.repo.guardar(doc)
        ya = {reserva["producto_id"] for reserva in doc["saga"]["reservas"]}
        for item in doc["items"]:
            if item["producto_id"] in ya:
                continue
            reserva = await self.catalogo.reservar(item["producto_id"], doc["pedido_id"], item["cantidad"])
            if reserva is None:
                doc["saga"]["compensacion"] = "SIN_STOCK"
                await self.repo.guardar(doc)
                await self._compensar(doc)
                return
            doc["saga"]["reservas"].append(
                {
                    "reserva_id": reserva["reserva_id"],
                    "producto_id": item["producto_id"],
                    "cantidad": item["cantidad"],
                    "liberada": False,
                    "confirmada": False,
                }
            )
            await self.repo.guardar(doc)
            logger.info("reservado %s para %s", reserva["reserva_id"], doc["pedido_id"])
        doc["saga"]["paso"] = "RESERVADO"
        await self.repo.guardar(doc)

    async def _pagar(self, doc: dict):
        pago = doc["pago"]
        if not pago.get("estado_pago"):
            if pago_aprobado(pago):
                pago["estado_pago"] = "APROBADO"
                pago["transaccion_id"] = f"tx_{uuid.uuid4().hex[:8]}"
                await self.repo.guardar(doc)
            else:
                pago["estado_pago"] = "RECHAZADO"
                pago["transaccion_id"] = None
                doc["saga"]["compensacion"] = "PAGO_RECHAZADO"
                await self.repo.guardar(doc)
                await self._compensar(doc)
                return
        doc["saga"]["paso"] = "PAGO_APROBADO"
        await self.repo.guardar(doc)
        logger.info("pago %s en %s", pago["estado_pago"], doc["pedido_id"])

    async def _confirmar(self, doc: dict):
        for reserva in doc["saga"]["reservas"]:
            if reserva.get("confirmada"):
                continue
            await self.catalogo.confirmar(reserva["reserva_id"])
            reserva["confirmada"] = True
            await self.repo.guardar(doc)
        doc["estado"] = "CONFIRMADO"
        doc["saga"]["paso"] = "CONFIRMADO"
        await self.repo.guardar(doc)
        logger.info("pedido confirmado %s", doc["pedido_id"])

    async def _compensar(self, doc: dict):
        for reserva in doc["saga"]["reservas"]:
            if reserva.get("liberada"):
                continue
            await self.catalogo.liberar(reserva["reserva_id"])
            reserva["liberada"] = True
            await self.repo.guardar(doc)
        motivo = doc["saga"].get("compensacion")
        if motivo == "SIN_STOCK":
            doc["estado"] = "RECHAZADO"
            doc["saga"]["paso"] = "RECHAZADO"
        else:
            doc["estado"] = "CANCELADO"
            doc["saga"]["paso"] = "CANCELADO"
        await self.repo.guardar(doc)
        logger.info("pedido %s compensado: %s", doc["pedido_id"], doc["estado"])
