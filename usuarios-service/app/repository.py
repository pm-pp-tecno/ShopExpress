from pymongo.errors import DuplicateKeyError


class UsuarioRepository:
    def __init__(self, mongo):
        self.col = mongo["usuarios"]["usuarios"]

    async def ensure_indexes(self):
        await self.col.create_index("id", unique=True)
        await self.col.create_index("email", unique=True)

    async def insertar(self, doc: dict):
        try:
            await self.col.insert_one(doc)
        except DuplicateKeyError as exc:
            raise ValueError("El email o el id ya existe") from exc

    async def obtener(self, usuario_id: str):
        return await self.col.find_one({"id": usuario_id})

    @staticmethod
    def publico(doc: dict) -> dict:
        return {
            "id": doc["id"],
            "tipo_documento": doc["tipo_documento"],
            "nro_documento": doc["nro_documento"],
            "nombre": doc["nombre"],
            "apellido": doc["apellido"],
            "email": doc["email"],
            "direcciones": doc.get("direcciones", []),
        }
