from fastapi import APIRouter, Query, Request
from fastapi.responses import JSONResponse

from app.models import UsuarioCreate
from app.service import UsuarioService

router = APIRouter()


def servicio(request: Request) -> UsuarioService:
    return request.app.state.service


@router.post("/api/usuarios", status_code=201, summary="Crea un usuario")
async def crear_usuario(datos: UsuarioCreate, request: Request):
    return await servicio(request).crear(datos)


@router.get("/api/usuarios/{usuario_id}", summary="Recupera un usuario y, si se pide, su historial")
async def obtener_usuario(
    usuario_id: str,
    request: Request,
    historial: bool = Query(default=True),
):
    datos = await servicio(request).obtener(usuario_id, incluir_historial=historial)
    return JSONResponse(content=datos)
