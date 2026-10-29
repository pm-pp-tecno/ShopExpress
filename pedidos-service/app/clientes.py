import httpx


class SagaPendiente(Exception):
    pass


class CatalogoCliente:
    def __init__(self, http: httpx.AsyncClient, base: str):
        self.http = http
        self.base = base

    async def obtener_producto(self, producto_id: str):
        respuesta = await self.http.get(f"{self.base}/api/productos/{producto_id}")
        if respuesta.status_code == 404:
            return None
        respuesta.raise_for_status()
        return respuesta.json()

    async def reservar(self, producto_id: str, pedido_id: str, cantidad: int):
        respuesta = await self.http.post(
            f"{self.base}/api/inventario/reservas",
            json={"producto_id": producto_id, "pedido_id": pedido_id, "cantidad": cantidad},
        )
        if respuesta.status_code == 409:
            return None
        if respuesta.status_code >= 400:
            raise SagaPendiente(respuesta.text)
        return respuesta.json()

    async def confirmar(self, reserva_id: str):
        respuesta = await self.http.post(f"{self.base}/api/inventario/reservas/{reserva_id}/confirmar")
        if respuesta.status_code >= 500:
            raise SagaPendiente(respuesta.text)
        respuesta.raise_for_status()

    async def liberar(self, reserva_id: str):
        respuesta = await self.http.post(f"{self.base}/api/inventario/reservas/{reserva_id}/liberar")
        if respuesta.status_code >= 500:
            raise SagaPendiente(respuesta.text)
        respuesta.raise_for_status()


class UsuariosCliente:
    def __init__(self, http: httpx.AsyncClient, base: str):
        self.http = http
        self.base = base

    async def obtener(self, usuario_id: str):
        respuesta = await self.http.get(
            f"{self.base}/api/usuarios/{usuario_id}",
            params={"historial": "false"},
        )
        if respuesta.status_code == 404:
            return None
        respuesta.raise_for_status()
        return respuesta.json()
