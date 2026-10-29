from decimal import Decimal

from pydantic import BaseModel, Field, field_validator


def dinero(valor: Decimal) -> float:
    return float(valor.quantize(Decimal("0.01")))


class ProductoCreate(BaseModel):
    nombre: str = Field(min_length=1)
    descripcion: str = ""
    precio: Decimal
    categoria_id: str = Field(min_length=1)
    categoria_nombre: str = Field(min_length=1)
    marca_id: str = Field(min_length=1)
    marca_nombre: str = Field(min_length=1)
    stock_inicial: int = Field(ge=0)
    relacionados: list[str] = []
    id: str | None = None
    activo: bool = True

    @field_validator("precio", mode="before")
    @classmethod
    def como_decimal(cls, valor):
        numero = Decimal(str(valor))
        if numero <= 0:
            raise ValueError("El precio debe ser mayor a 0")
        return numero.quantize(Decimal("0.01"))


class ReservaCreate(BaseModel):
    producto_id: str = Field(min_length=1)
    pedido_id: str = Field(min_length=1)
    cantidad: int = Field(ge=1)
