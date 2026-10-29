from fastapi import APIRouter, Request, Response

from app.models import ProductoCreate, ReservaCreate
from app.service import CatalogoService

router = APIRouter()


def servicio(request: Request) -> CatalogoService:
    return request.app.state.service


@router.post("/api/productos", summary="Crea un producto en el grafo y su inventario")
async def crear_producto(datos: ProductoCreate, request: Request, response: Response):
    ficha, creado = await servicio(request).crear(datos)
    response.status_code = 201 if creado else 200
    return ficha


@router.get("/api/productos", summary="Lista productos con stock")
async def listar_productos(request: Request):
    return await servicio(request).listar()


@router.get("/api/productos/{producto_id}", summary="Ficha del producto y stock disponible")
async def obtener_producto(producto_id: str, request: Request):
    return await servicio(request).obtener(producto_id)


@router.get("/api/productos/{producto_id}/relacionados", summary="Productos relacionados en Neo4j")
async def relacionados(producto_id: str, request: Request):
    return await servicio(request).relacionados(producto_id)


@router.post("/api/inventario/reservas", summary="Reserva stock de forma atómica")
async def reservar(datos: ReservaCreate, request: Request, response: Response):
    reserva, creada = await servicio(request).reservar(datos)
    response.status_code = 201 if creada else 200
    return reserva


@router.post("/api/inventario/reservas/{reserva_id}/confirmar", summary="Confirma una reserva sin volver a descontar")
async def confirmar(reserva_id: str, request: Request):
    return await servicio(request).confirmar(reserva_id)


@router.post("/api/inventario/reservas/{reserva_id}/liberar", summary="Devuelve el stock de una reserva activa")
async def liberar(reserva_id: str, request: Request):
    return await servicio(request).liberar(reserva_id)
