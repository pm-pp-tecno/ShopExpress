import uuid

from fastapi import HTTPException

from app.models import ProductoCreate, ReservaCreate
from app.repository import GrafoRepository, InventarioRepository, ficha


def nuevo_id(prefijo: str) -> str:
    return f"{prefijo}_{uuid.uuid4().hex[:8]}"


class CatalogoService:
    def __init__(self, inventario: InventarioRepository, grafo: GrafoRepository):
        self.inventario = inventario
        self.grafo = grafo

    async def crear(self, datos: ProductoCreate) -> tuple[dict, bool]:
        for otro in datos.relacionados:
            if not await self.grafo.existe(otro):
                raise HTTPException(status_code=400, detail=f"No existe el producto relacionado {otro}")
        producto_id = datos.id or nuevo_id("prod")
        if producto_id in datos.relacionados:
            raise HTTPException(status_code=400, detail="Un producto no se relaciona consigo mismo")
        tenia_grafo = await self.grafo.existe(producto_id)
        tenia_inv = await self.inventario.existe(producto_id)
        creo_grafo = False
        creo_inv = False
        try:
            if not tenia_grafo:
                await self.grafo.merge_producto(
                    {
                        "id": producto_id,
                        "nombre": datos.nombre,
                        "descripcion": datos.descripcion,
                        "precio": str(datos.precio),
                        "activo": datos.activo,
                        "categoria_id": datos.categoria_id,
                        "categoria_nombre": datos.categoria_nombre,
                        "marca_id": datos.marca_id,
                        "marca_nombre": datos.marca_nombre,
                    }
                )
                creo_grafo = True
            if not tenia_inv:
                await self.inventario.crear(producto_id, datos.stock_inicial)
                creo_inv = True
            for otro in datos.relacionados:
                await self.grafo.relacionar(producto_id, otro)
        except HTTPException:
            raise
        except Exception:
            if creo_inv:
                await self.inventario.borrar(producto_id)
            if creo_grafo:
                await self.grafo.borrar_producto(producto_id)
            raise
        return await self.obtener(producto_id), not (tenia_grafo and tenia_inv)

    async def obtener(self, producto_id: str) -> dict:
        grafo = await self.grafo.obtener(producto_id)
        if not grafo:
            raise HTTPException(status_code=404, detail="Producto no encontrado")
        inventario = await self.inventario.obtener(producto_id)
        if not inventario:
            raise HTTPException(status_code=409, detail="El producto no tiene inventario")
        return ficha(grafo, inventario)

    async def listar(self) -> list[dict]:
        inventarios = await self.inventario.listar()
        fichas = []
        for grafo in await self.grafo.listar():
            inventario = inventarios.get(grafo["id"])
            if inventario:
                fichas.append(ficha(grafo, inventario))
        return fichas

    async def relacionados(self, producto_id: str) -> dict:
        if not await self.grafo.existe(producto_id):
            raise HTTPException(status_code=404, detail="Producto no encontrado")
        return {"producto_id": producto_id, "relacionados": await self.grafo.relacionados(producto_id)}

    async def reservar(self, datos: ReservaCreate) -> tuple[dict, bool]:
        if not await self.inventario.existe(datos.producto_id):
            raise HTTPException(status_code=404, detail="No hay inventario para el producto")
        existente = await self.inventario.reserva_del_pedido(datos.producto_id, datos.pedido_id)
        if existente:
            if existente["cantidad"] != datos.cantidad:
                raise HTTPException(status_code=409, detail="La reserva existente tiene otra cantidad")
            return existente, False
        reserva_id = nuevo_id("res")
        actualizado = await self.inventario.reservar(
            datos.producto_id, datos.pedido_id, datos.cantidad, reserva_id
        )
        if actualizado:
            for reserva in actualizado["reservas"]:
                if reserva["reserva_id"] == reserva_id:
                    return reserva, True
        de_nuevo = await self.inventario.reserva_del_pedido(datos.producto_id, datos.pedido_id)
        if de_nuevo:
            return de_nuevo, False
        raise HTTPException(status_code=409, detail="Sin stock")

    async def confirmar(self, reserva_id: str) -> dict:
        actualizado = await self.inventario.confirmar(reserva_id)
        if actualizado:
            return {"reserva_id": reserva_id, "estado": "CONFIRMADA"}
        reserva = await self.inventario.por_reserva(reserva_id)
        if not reserva:
            raise HTTPException(status_code=404, detail="Reserva no encontrada")
        if reserva["estado"] == "CONFIRMADA":
            return {"reserva_id": reserva_id, "estado": "CONFIRMADA"}
        raise HTTPException(status_code=409, detail="La reserva no está activa")

    async def liberar(self, reserva_id: str) -> dict:
        reserva = await self.inventario.por_reserva(reserva_id)
        if not reserva:
            raise HTTPException(status_code=404, detail="Reserva no encontrada")
        if reserva["estado"] == "LIBERADA":
            return {"reserva_id": reserva_id, "estado": "LIBERADA"}
        if reserva["estado"] != "ACTIVA":
            raise HTTPException(status_code=409, detail="La reserva no está activa")
        actualizado = await self.inventario.liberar(reserva_id, reserva["cantidad"])
        if actualizado:
            return {"reserva_id": reserva_id, "estado": "LIBERADA"}
        reserva = await self.inventario.por_reserva(reserva_id)
        if reserva and reserva["estado"] == "LIBERADA":
            return {"reserva_id": reserva_id, "estado": "LIBERADA"}
        raise HTTPException(status_code=409, detail="No se pudo liberar la reserva")
