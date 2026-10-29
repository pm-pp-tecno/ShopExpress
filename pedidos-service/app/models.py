from decimal import Decimal

from pydantic import BaseModel


def dinero(valor: Decimal) -> float:
    return float(valor.quantize(Decimal("0.01")))


class ItemIn(BaseModel):
    producto_id: str
    cantidad: int


class PagoIn(BaseModel):
    metodo: str = ""
    resultado: str | None = None


class PedidoIn(BaseModel):
    usuario_id: str = ""
    items: list[ItemIn] = []
    pago: PagoIn
    idempotency_key: str | None = None


def pedido_publico(doc: dict) -> dict:
    return {
        "pedido_id": doc["pedido_id"],
        "usuario_id": doc["usuario_id"],
        "estado": doc["estado"],
        "items": [
            {
                "producto_id": item["producto_id"],
                "cantidad": item["cantidad"],
                "precio_unitario": dinero(Decimal(item["precio_unitario"])),
            }
            for item in doc["items"]
        ],
        "total": dinero(Decimal(doc["total"])),
        "pago": {
            "metodo": doc["pago"]["metodo"],
            "estado_pago": doc["pago"].get("estado_pago"),
            "transaccion_id": doc["pago"].get("transaccion_id"),
        },
        "saga_paso": doc["saga"]["paso"],
    }
