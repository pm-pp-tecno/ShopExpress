from pydantic import BaseModel, Field


class Direccion(BaseModel):
    calle: str = Field(min_length=1)
    ciudad: str = Field(min_length=1)
    codigo_postal: str = Field(min_length=1)


class UsuarioCreate(BaseModel):
    tipo_documento: str = Field(min_length=1)
    nro_documento: str = Field(min_length=1)
    nombre: str = Field(min_length=1)
    apellido: str = Field(min_length=1)
    email: str = Field(min_length=3)
    direcciones: list[Direccion] = []
    id: str | None = None
