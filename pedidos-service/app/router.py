import httpx
from fastapi import APIRouter, Header, HTTPException, Query, Request
from fastapi.responses import JSONResponse

from app.chain import ChainAbort
from app.clientes import SagaPendiente
from app.models import PedidoIn, pedido_publico

router = APIRouter()


def servicio(request: Request):
    return request.app.state.service


@router.post("/api/pedidos", summary="Valida el pedido y ejecuta la SAGA")
async def crear_pedido(
    datos: PedidoIn,
    request: Request,
    idempotency_key: str | None = Header(default=None, alias="Idempotency-Key"),
    x_pausar_saga: str | None = Header(default=None, alias="X-Pausar-Saga"),
):
    pausar = x_pausar_saga if x_pausar_saga == "RESERVADO" else None
    try:
        doc = await servicio(request).crear(datos, idempotency_key, pausar)
    except ChainAbort as exc:
        raise HTTPException(status_code=exc.status_code, detail=exc.detail) from exc
    except SagaPendiente as exc:
        raise HTTPException(
            status_code=503,
            detail="La SAGA quedó pendiente. Se retoma al reiniciar Pedidos o con POST /api/pedidos/reanudar",
        ) from exc
    except httpx.HTTPError as exc:
        raise HTTPException(status_code=503, detail="No se pudo completar la SAGA") from exc
    return JSONResponse(content=pedido_publico(doc))


@router.get("/api/pedidos", summary="Pedidos de un usuario, fuente del historial")
async def listar_pedidos(request: Request, usuario_id: str = Query(min_length=1)):
    docs = await servicio(request).por_usuario(usuario_id)
    return [pedido_publico(doc) for doc in docs]


@router.get("/api/pedidos/{pedido_id}", summary="Recupera un pedido")
async def obtener_pedido(pedido_id: str, request: Request):
    doc = await servicio(request).obtener(pedido_id)
    if not doc:
        raise HTTPException(status_code=404, detail="Pedido no encontrado")
    return pedido_publico(doc)


@router.post("/api/pedidos/reanudar", summary="Retoma las SAGA pendientes, la misma lógica del arranque")
async def reanudar(request: Request):
    ids = await servicio(request).reanudar()
    pedidos = []
    for pedido_id in ids:
        doc = await servicio(request).obtener(pedido_id)
        if doc:
            pedidos.append(pedido_publico(doc))
    return {"reanudados": ids, "pedidos": pedidos}
