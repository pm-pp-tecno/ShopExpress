class PedidoRepository:
    def __init__(self, mongo):
        self.col = mongo["pedidos"]["pedidos"]

    async def ensure_indexes(self):
        await self.col.create_index("pedido_id", unique=True)
        await self.col.create_index("idempotency_key", unique=True)
        await self.col.create_index("usuario_id")

    async def insertar(self, doc: dict):
        await self.col.insert_one(doc)

    async def guardar(self, doc: dict):
        await self.col.replace_one({"_id": doc["_id"]}, doc)

    async def obtener(self, pedido_id: str):
        return await self.col.find_one({"_id": pedido_id})

    async def por_clave(self, clave: str):
        return await self.col.find_one({"idempotency_key": clave})

    async def por_usuario(self, usuario_id: str):
        cursor = self.col.find({"usuario_id": usuario_id})
        return await cursor.to_list(length=500)

    async def pendientes(self):
        cursor = self.col.find({"estado": "PENDIENTE"})
        return await cursor.to_list(length=500)
