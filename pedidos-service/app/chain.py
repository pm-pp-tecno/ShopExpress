from decimal import Decimal

import httpx

from app.clientes import CatalogoCliente, UsuariosCliente
from app.models import PedidoIn


class ChainAbort(Exception):
    def __init__(self, status_code: int, detail: str):
        self.status_code = status_code
        self.detail = detail


class Contexto:
    def __init__(self, datos: PedidoIn, usuarios: UsuariosCliente, catalogo: CatalogoCliente):
        self.datos = datos
        self.usuarios = usuarios
        self.catalogo = catalogo
        self.items: list[dict] = []
        self.total = Decimal("0.00")


class Manejador:
    def __init__(self, siguiente: "Manejador | None" = None):
        self.siguiente = siguiente

    async def handle(self, ctx: Contexto):
        await self.ejecutar(ctx)
        if self.siguiente:
            await self.siguiente.handle(ctx)

    async def ejecutar(self, ctx: Contexto):
        raise NotImplementedError


class ValidarDatos(Manejador):
    async def ejecutar(self, ctx: Contexto):
        if not ctx.datos.usuario_id:
            raise ChainAbort(400, "Falta el usuario")
        if not ctx.datos.items:
            raise ChainAbort(400, "El pedido no tiene ítems")
        if not ctx.datos.pago.metodo:
            raise ChainAbort(400, "Falta el método de pago")
        vistos = set()
        for item in ctx.datos.items:
            if item.cantidad < 1:
                raise ChainAbort(400, "La cantidad debe ser mayor a 0")
            if item.producto_id in vistos:
                raise ChainAbort(400, "El producto está repetido en el pedido")
            vistos.add(item.producto_id)


class ValidarUsuario(Manejador):
    async def ejecutar(self, ctx: Contexto):
        try:
            usuario = await ctx.usuarios.obtener(ctx.datos.usuario_id)
        except httpx.HTTPError as exc:
            raise ChainAbort(503, "No se pudo consultar Usuarios") from exc
        if usuario is None:
            raise ChainAbort(404, "Usuario no encontrado")


class ValidarProductosYCantidades(Manejador):
    async def ejecutar(self, ctx: Contexto):
        for item in ctx.datos.items:
            try:
                producto = await ctx.catalogo.obtener_producto(item.producto_id)
            except httpx.HTTPError as exc:
                raise ChainAbort(503, "No se pudo consultar Catálogo") from exc
            if producto is None:
                raise ChainAbort(404, f"Producto no encontrado: {item.producto_id}")
            if not producto.get("activo", True):
                raise ChainAbort(400, f"Producto inactivo: {item.producto_id}")
            ctx.items.append(
                {
                    "producto_id": item.producto_id,
                    "cantidad": item.cantidad,
                    "precio": Decimal(str(producto["precio"])),
                }
            )


class PrepararPedido(Manejador):
    async def ejecutar(self, ctx: Contexto):
        total = Decimal("0.00")
        preparados = []
        for item in ctx.items:
            precio = item["precio"].quantize(Decimal("0.01"))
            total += precio * item["cantidad"]
            preparados.append(
                {
                    "producto_id": item["producto_id"],
                    "cantidad": item["cantidad"],
                    "precio_unitario": str(precio),
                }
            )
        ctx.items = preparados
        ctx.total = total.quantize(Decimal("0.01"))


def construir_cadena() -> ValidarDatos:
    return ValidarDatos(ValidarUsuario(ValidarProductosYCantidades(PrepararPedido())))
