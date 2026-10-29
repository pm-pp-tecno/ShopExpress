import os
import uuid
from concurrent.futures import ThreadPoolExecutor

import httpx
import pytest

USUARIOS = os.getenv("USUARIOS_URL", "http://localhost:8001")
CATALOGO = os.getenv("CATALOGO_URL", "http://localhost:8002")
PEDIDOS = os.getenv("PEDIDOS_URL", "http://localhost:8003")


@pytest.fixture(scope="session", autouse=True)
def servicios_arriba():
    for url in (f"{USUARIOS}/health", f"{CATALOGO}/health", f"{PEDIDOS}/health"):
        try:
            respuesta = httpx.get(url, timeout=3)
            respuesta.raise_for_status()
        except Exception as exc:
            pytest.fail(f"No responde {url}. Levantá el sistema con docker compose up --build -d. {exc}")


def _usuario():
    sufijo = uuid.uuid4().hex[:8]
    respuesta = httpx.post(
        f"{USUARIOS}/api/usuarios",
        json={
            "tipo_documento": "DNI",
            "nro_documento": sufijo,
            "nombre": "Juan",
            "apellido": "Pérez",
            "email": f"juan.{sufijo}@example.com",
            "direcciones": [
                {"calle": "Av. Principal 123", "ciudad": "Montevideo", "codigo_postal": "11000"}
            ],
        },
        timeout=15,
    )
    assert respuesta.status_code == 201, respuesta.text
    return respuesta.json()


def _producto(stock, precio="25.50", relacionados=None, nombre="Auriculares"):
    respuesta = httpx.post(
        f"{CATALOGO}/api/productos",
        json={
            "nombre": nombre,
            "descripcion": "Auriculares inalámbricos",
            "precio": precio,
            "categoria_id": "cat_audio",
            "categoria_nombre": "Audio",
            "marca_id": "marca_01",
            "marca_nombre": "Acme",
            "stock_inicial": stock,
            "relacionados": relacionados or [],
        },
        timeout=15,
    )
    assert respuesta.status_code == 201, respuesta.text
    return respuesta.json()


def _pedido(usuario_id, items, metodo="TARJETA_CREDITO", clave=None, headers=None):
    cuerpo = {
        "usuario_id": usuario_id,
        "items": items,
        "pago": {"metodo": metodo},
    }
    if clave:
        cuerpo["idempotency_key"] = clave
    return httpx.post(f"{PEDIDOS}/api/pedidos", json=cuerpo, headers=headers, timeout=20)


def _stock(producto_id):
    respuesta = httpx.get(f"{CATALOGO}/api/productos/{producto_id}", timeout=10)
    assert respuesta.status_code == 200, respuesta.text
    return respuesta.json()["disponible"]


def test_relacion_de_neo4j_y_stock():
    primero = _producto(10, nombre="Auriculares")
    segundo = _producto(5, nombre="Estuche", relacionados=[primero["id"]])
    respuesta = httpx.get(f"{CATALOGO}/api/productos/{segundo['id']}/relacionados", timeout=10)
    assert respuesta.status_code == 200
    ids = [item["id"] for item in respuesta.json()["relacionados"]]
    assert primero["id"] in ids
    assert _stock(primero["id"]) == 10


def test_pedido_confirmado_descuenta_stock_y_figura_en_el_historial():
    usuario = _usuario()
    producto = _producto(10)
    clave = f"idem-{uuid.uuid4().hex}"
    respuesta = _pedido(usuario["id"], [{"producto_id": producto["id"], "cantidad": 2}], clave=clave)
    assert respuesta.status_code == 200, respuesta.text
    pedido = respuesta.json()
    assert pedido["estado"] == "CONFIRMADO"
    assert pedido["pago"]["estado_pago"] == "APROBADO"
    assert pedido["total"] == 51.0
    assert pedido["items"][0]["precio_unitario"] == 25.5
    assert _stock(producto["id"]) == 8

    repetido = _pedido(usuario["id"], [{"producto_id": producto["id"], "cantidad": 2}], clave=clave)
    assert repetido.status_code == 200
    assert repetido.json()["pedido_id"] == pedido["pedido_id"]
    assert repetido.json()["pago"]["transaccion_id"] == pedido["pago"]["transaccion_id"]
    assert _stock(producto["id"]) == 8

    historial = httpx.get(f"{USUARIOS}/api/usuarios/{usuario['id']}", timeout=10)
    assert historial.status_code == 200
    ids = [item["pedido_id"] for item in historial.json()["historial_compras"]]
    assert pedido["pedido_id"] in ids


def test_sin_stock_no_descuenta():
    usuario = _usuario()
    producto = _producto(5)
    respuesta = _pedido(usuario["id"], [{"producto_id": producto["id"], "cantidad": 100}])
    assert respuesta.status_code == 200, respuesta.text
    assert respuesta.json()["estado"] == "RECHAZADO"
    assert _stock(producto["id"]) == 5


def test_pago_rechazado_libera_la_reserva():
    usuario = _usuario()
    producto = _producto(5)
    respuesta = _pedido(
        usuario["id"],
        [{"producto_id": producto["id"], "cantidad": 2}],
        metodo="TARJETA_RECHAZADA",
    )
    assert respuesta.status_code == 200, respuesta.text
    cuerpo = respuesta.json()
    assert cuerpo["estado"] == "CANCELADO"
    assert cuerpo["pago"]["estado_pago"] == "RECHAZADO"
    assert _stock(producto["id"]) == 5


def test_compensa_la_reserva_parcial_si_el_segundo_item_no_tiene_stock():
    usuario = _usuario()
    con_stock = _producto(4, nombre="Con stock")
    sin_stock = _producto(0, nombre="Sin stock")
    respuesta = _pedido(
        usuario["id"],
        [
            {"producto_id": con_stock["id"], "cantidad": 1},
            {"producto_id": sin_stock["id"], "cantidad": 1},
        ],
    )
    assert respuesta.status_code == 200, respuesta.text
    assert respuesta.json()["estado"] == "RECHAZADO"
    assert _stock(con_stock["id"]) == 4
    assert _stock(sin_stock["id"]) == 0


def test_dos_compras_simultaneas_de_la_ultima_unidad():
    usuario = _usuario()
    producto = _producto(1, precio="10.00")

    def comprar():
        return _pedido(
            usuario["id"],
            [{"producto_id": producto["id"], "cantidad": 1}],
            clave=f"idem-{uuid.uuid4().hex}",
        )

    with ThreadPoolExecutor(max_workers=2) as pool:
        respuestas = list(pool.map(lambda _: comprar(), range(2)))
    assert [r.status_code for r in respuestas] == [200, 200]
    estados = sorted(r.json()["estado"] for r in respuestas)
    assert estados == ["CONFIRMADO", "RECHAZADO"]
    assert _stock(producto["id"]) == 0


def test_reanudar_no_vuelve_a_cobrar_ni_a_descontar():
    usuario = _usuario()
    producto = _producto(6)
    respuesta = _pedido(
        usuario["id"],
        [{"producto_id": producto["id"], "cantidad": 2}],
        headers={"X-Pausar-Saga": "RESERVADO"},
    )
    assert respuesta.status_code == 200, respuesta.text
    pausado = respuesta.json()
    assert pausado["estado"] == "PENDIENTE"
    assert pausado["saga_paso"] == "RESERVADO"
    assert pausado["pago"]["transaccion_id"] is None
    assert _stock(producto["id"]) == 4

    reanudado = httpx.post(f"{PEDIDOS}/api/pedidos/reanudar", timeout=20)
    assert reanudado.status_code == 200, reanudado.text
    pedido = next(item for item in reanudado.json()["pedidos"] if item["pedido_id"] == pausado["pedido_id"])
    assert pedido["estado"] == "CONFIRMADO"
    assert pedido["pago"]["estado_pago"] == "APROBADO"
    transaccion = pedido["pago"]["transaccion_id"]
    assert transaccion
    assert _stock(producto["id"]) == 4

    otra_vez = httpx.post(f"{PEDIDOS}/api/pedidos/reanudar", timeout=20)
    assert otra_vez.status_code == 200
    pedido = httpx.get(f"{PEDIDOS}/api/pedidos/{pausado['pedido_id']}", timeout=10).json()
    assert pedido["pago"]["transaccion_id"] == transaccion
    assert _stock(producto["id"]) == 4


def test_la_cadena_rechaza_antes_de_tocar_stock():
    usuario = _usuario()
    producto = _producto(3)
    vacio = _pedido(usuario["id"], [])
    assert vacio.status_code == 400
    inexistente = _pedido("usr_no_existe", [{"producto_id": producto["id"], "cantidad": 1}])
    assert inexistente.status_code == 404
    assert _stock(producto["id"]) == 3
