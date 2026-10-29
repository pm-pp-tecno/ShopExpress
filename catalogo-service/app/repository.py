from decimal import Decimal

from pymongo import ReturnDocument
from pymongo.errors import DuplicateKeyError

from app.models import dinero


class InventarioRepository:
    def __init__(self, mongo):
        self.col = mongo["inventario"]["productos"]

    async def ensure_indexes(self):
        await self.col.create_index("producto_id", unique=True)
        await self.col.create_index("reservas.reserva_id")

    async def existe(self, producto_id: str) -> bool:
        return await self.col.count_documents({"_id": producto_id}, limit=1) == 1

    async def obtener(self, producto_id: str):
        return await self.col.find_one({"_id": producto_id})

    async def listar(self) -> dict:
        cursor = self.col.find({})
        docs = await cursor.to_list(length=1000)
        return {doc["producto_id"]: doc for doc in docs}

    async def crear(self, producto_id: str, disponible: int):
        try:
            await self.col.insert_one(
                {
                    "_id": producto_id,
                    "producto_id": producto_id,
                    "disponible": disponible,
                    "reservas": [],
                }
            )
        except DuplicateKeyError:
            return

    async def borrar(self, producto_id: str):
        await self.col.delete_one({"_id": producto_id})

    async def reserva_del_pedido(self, producto_id: str, pedido_id: str):
        doc = await self.obtener(producto_id)
        if not doc:
            return None
        for reserva in doc.get("reservas", []):
            if reserva["pedido_id"] == pedido_id and reserva["estado"] in ("ACTIVA", "CONFIRMADA"):
                return reserva
        return None

    async def reservar(self, producto_id: str, pedido_id: str, cantidad: int, reserva_id: str):
        filtro = {
            "_id": producto_id,
            "disponible": {"$gte": cantidad},
            "reservas": {
                "$not": {
                    "$elemMatch": {
                        "pedido_id": pedido_id,
                        "estado": {"$in": ["ACTIVA", "CONFIRMADA"]},
                    }
                }
            },
        }
        reserva = {
            "reserva_id": reserva_id,
            "pedido_id": pedido_id,
            "cantidad": cantidad,
            "estado": "ACTIVA",
        }
        return await self.col.find_one_and_update(
            filtro,
            {"$inc": {"disponible": -cantidad}, "$push": {"reservas": reserva}},
            return_document=ReturnDocument.AFTER,
        )

    def _buscar(self, doc: dict, reserva_id: str):
        for reserva in doc.get("reservas", []):
            if reserva["reserva_id"] == reserva_id:
                return reserva
        return None

    async def por_reserva(self, reserva_id: str):
        doc = await self.col.find_one(
            {"reservas.reserva_id": reserva_id},
            {"reservas.$": 1, "producto_id": 1, "disponible": 1},
        )
        if not doc:
            return None
        return doc["reservas"][0]

    async def confirmar(self, reserva_id: str):
        return await self.col.find_one_and_update(
            {"reservas": {"$elemMatch": {"reserva_id": reserva_id, "estado": "ACTIVA"}}},
            {"$set": {"reservas.$.estado": "CONFIRMADA"}},
            return_document=ReturnDocument.AFTER,
        )

    async def liberar(self, reserva_id: str, cantidad: int):
        return await self.col.find_one_and_update(
            {
                "reservas": {
                    "$elemMatch": {
                        "reserva_id": reserva_id,
                        "estado": "ACTIVA",
                        "cantidad": cantidad,
                    }
                }
            },
            {"$set": {"reservas.$.estado": "LIBERADA"}, "$inc": {"disponible": cantidad}},
            return_document=ReturnDocument.AFTER,
        )


class GrafoRepository:
    def __init__(self, driver):
        self.driver = driver

    async def _run(self, query: str, **params):
        async with self.driver.session() as session:
            result = await session.run(query, params)
            return await result.data()

    async def ensure_constraints(self):
        for query in (
            "CREATE CONSTRAINT producto_id IF NOT EXISTS FOR (p:Producto) REQUIRE p.id IS UNIQUE",
            "CREATE CONSTRAINT categoria_id IF NOT EXISTS FOR (c:Categoria) REQUIRE c.id IS UNIQUE",
            "CREATE CONSTRAINT marca_id IF NOT EXISTS FOR (m:Marca) REQUIRE m.id IS UNIQUE",
        ):
            await self._run(query)

    async def ping(self):
        await self._run("RETURN 1 AS ok")

    async def existe(self, producto_id: str) -> bool:
        filas = await self._run("MATCH (p:Producto {id: $id}) RETURN p.id AS id", id=producto_id)
        return bool(filas)

    async def obtener(self, producto_id: str):
        filas = await self._run(
            """
            MATCH (p:Producto {id: $id})
            OPTIONAL MATCH (p)-[:PERTENECE_A]->(c:Categoria)
            OPTIONAL MATCH (p)-[:FABRICADO_POR]->(m:Marca)
            RETURN p.id AS id, p.nombre AS nombre, p.descripcion AS descripcion,
                   p.precio AS precio, p.activo AS activo,
                   c.id AS categoria_id, m.id AS marca_id
            """,
            id=producto_id,
        )
        return filas[0] if filas else None

    async def listar(self):
        return await self._run(
            """
            MATCH (p:Producto)
            OPTIONAL MATCH (p)-[:PERTENECE_A]->(c:Categoria)
            OPTIONAL MATCH (p)-[:FABRICADO_POR]->(m:Marca)
            RETURN p.id AS id, p.nombre AS nombre, p.descripcion AS descripcion,
                   p.precio AS precio, p.activo AS activo,
                   c.id AS categoria_id, m.id AS marca_id
            ORDER BY p.id
            """
        )

    async def merge_producto(self, datos: dict):
        await self._run(
            """
            MERGE (c:Categoria {id: $categoria_id})
              ON CREATE SET c.nombre = $categoria_nombre
              ON MATCH SET c.nombre = $categoria_nombre
            MERGE (m:Marca {id: $marca_id})
              ON CREATE SET m.nombre = $marca_nombre
              ON MATCH SET m.nombre = $marca_nombre
            MERGE (p:Producto {id: $id})
              ON CREATE SET p.nombre = $nombre, p.descripcion = $descripcion,
                            p.precio = $precio, p.activo = $activo
              ON MATCH SET p.nombre = $nombre, p.descripcion = $descripcion,
                           p.precio = $precio, p.activo = $activo
            MERGE (p)-[:PERTENECE_A]->(c)
            MERGE (p)-[:FABRICADO_POR]->(m)
            """,
            **datos,
        )

    async def borrar_producto(self, producto_id: str):
        await self._run("MATCH (p:Producto {id: $id}) DETACH DELETE p", id=producto_id)

    async def relacionar(self, producto_id: str, otro_id: str):
        await self._run(
            """
            MATCH (a:Producto {id: $id}), (b:Producto {id: $otro})
            MERGE (a)-[:RELACIONADO_CON]->(b)
            """,
            id=producto_id,
            otro=otro_id,
        )

    async def relacionados(self, producto_id: str):
        return await self._run(
            """
            MATCH (p:Producto {id: $id})-[:RELACIONADO_CON]-(o:Producto)
            RETURN DISTINCT o.id AS id, o.nombre AS nombre
            ORDER BY o.id
            """,
            id=producto_id,
        )


def ficha(grafo: dict, inventario: dict) -> dict:
    return {
        "id": grafo["id"],
        "nombre": grafo["nombre"],
        "descripcion": grafo.get("descripcion") or "",
        "precio": dinero(Decimal(str(grafo["precio"]))),
        "categoria_id": grafo["categoria_id"],
        "marca_id": grafo["marca_id"],
        "activo": bool(grafo["activo"]),
        "disponible": inventario["disponible"],
    }
