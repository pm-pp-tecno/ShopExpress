import uuid

import httpx
from fastapi import HTTPException

from app.models import UsuarioCreate
from app.repository import UsuarioRepository


def nuevo_id() -> str:
    return f"usr_{uuid.uuid4().hex[:8]}"


class UsuarioService:
    def __init__(self, repo: UsuarioRepository, http: httpx.AsyncClient, pedidos_url: str):
        self.repo = repo
        self.http = http
        self.pedidos_url = pedidos_url

    async def crear(self, datos: UsuarioCreate) -> dict:
        if "@" not in datos.email:
            raise HTTPException(status_code=400, detail="Email inválido")
        usuario_id = datos.id or nuevo_id()
        doc = {
            "_id": usuario_id,
            "id": usuario_id,
            "tipo_documento": datos.tipo_documento,
            "nro_documento": datos.nro_documento,
            "nombre": datos.nombre,
            "apellido": datos.apellido,
            "email": datos.email,
            "direcciones": [d.model_dump() for d in datos.direcciones],
        }
        try:
            await self.repo.insertar(doc)
        except ValueError as exc:
            raise HTTPException(status_code=409, detail=str(exc)) from exc
        return self.repo.publico(doc)

    async def obtener(self, usuario_id: str, incluir_historial: bool) -> dict:
        doc = await self.repo.obtener(usuario_id)
        if not doc:
            raise HTTPException(status_code=404, detail="Usuario no encontrado")
        publico = self.repo.publico(doc)
        if not incluir_historial:
            return publico
        try:
            respuesta = await self.http.get(
                f"{self.pedidos_url}/api/pedidos",
                params={"usuario_id": usuario_id},
            )
        except httpx.HTTPError as exc:
            raise HTTPException(status_code=503, detail="No se pudo leer el historial en Pedidos") from exc
        if respuesta.status_code >= 400:
            raise HTTPException(status_code=503, detail="No se pudo leer el historial en Pedidos")
        publico["historial_compras"] = respuesta.json()
        return publico
