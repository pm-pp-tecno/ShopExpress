# ShopExpress — Plan de preparación y desarrollo

**Laboratorio:** Tarea 2 NoSQL 2026 · **Estado:** planificación aprobada; implementación y pruebas pendientes · **Fecha:** 29/10/2026  
**Documento base:** `Tarea 2 NoSql  2026.pdf` (4 páginas). Este archivo registra decisiones del grupo y sirve de instrucciones para otra IA desarrolladora.

## 1. Qué pide la consigna

Diseñar e implementar **ShopExpress**, una plataforma ficticia de comercio electrónico con tres microservicios: **Usuarios**, **Catálogo e Inventario**, y **Pedidos y Pagos**.

- Usar **al menos dos bases NoSQL**, justificar el modelo de datos y cuándo **embeber** o **referenciar**.
- Priorizar lecturas rápidas de usuarios/catálogo (se admite consistencia eventual) y **consistencia fuerte al crear pedidos y descontar stock**: pedidos únicos y **sin sobreventa**.
- Implementar **SAGA orquestada** por Pedidos y Pagos (éxito y compensaciones), y **Chain of Responsibility** para validaciones.
- Endpoints obligatorios: `POST /api/usuarios`, `GET /api/usuarios/{usuario_id}`, `POST /api/productos`, `GET /api/productos/{producto_id}`, `POST /api/pedidos`.
- Opcional: `GET /api/usuarios/exportar` (datos anonimizados); mencionar CQRS/Event Sourcing/privacidad si aporta.
- Entregar **un repositorio Git** con código, Dockerfiles/Compose, README (decisiones, instrucciones, pruebas), diagramas de **arquitectura, SAGA y Chain**, colección Postman o equivalente y demo de **~10 minutos**. La consigna señala **5 y 12 de noviembre** como fechas de entrega/defensa; confirmar cuál corresponde al grupo.

## 2. Registro breve de las decisiones

| Tema | Alternativas discutidas | Decisión y motivo |
|---|---|---|
| Bases NoSQL | Neo4j protagonista, MongoDB predominante, grafo de clientes | **Neo4j + MongoDB**: mostrar usos diferenciados de grafo/documentos. |
| Catálogo | Documentos o grafo | **Neo4j**: productos, categorías, marcas y productos relacionados; aporta consultas de relaciones reales. |
| Stock | Primero se consideró Neo4j transaccional | **MongoDB**: reserva con actualización **atómica condicional** por producto; más simple de demostrar sin sobreventa. |
| Backend | Spring Boot, Node, FastAPI | **Python/FastAPI** para los tres servicios. |
| Interfaz | Back-office sencillo en Streamlit | **Descartado**: probar con Postman/Swagger; ningún frontend ni contenedor de pruebas permanente. |
| Integración | REST o mensajería | **REST/JSON** sin broker, gateway ni servicios adicionales. |
| Pruebas | Manuales y automatizadas | **Colección Postman CLI** + **Pytest/HTTPX** para concurrencia y recuperación. |

**Alcance cerrado:** **5 contenedores permanentes** (3 FastAPI, 1 Neo4j, 1 MongoDB), **3 microservicios**, **2 motores NoSQL**, un `docker-compose.yml`. No se construyeron todavía componentes ni se validaron los escenarios.

## 3. Arquitectura y propiedad de datos

```text
Postman / Swagger (fuera de Docker)
      |                 |                   |
Usuarios API       Catálogo API         Pedidos API
  FastAPI             FastAPI              FastAPI
    |                  |   |                  |
MongoDB/usuarios   Neo4j  MongoDB/inventario MongoDB/pedidos
                           ^                   |
                           +--- REST SAGA -----+
```

- **Usuarios**: perfil, documento, correo y direcciones en MongoDB. El historial de compras se obtiene del servicio de Pedidos, sin duplicarlo como fuente de verdad.
- **Catálogo e Inventario**: **único propietario** del grafo Neo4j y del inventario MongoDB; expone las operaciones de reserva, confirmación y liberación. Otros servicios **no acceden directamente** a sus bases.
- **Pedidos y Pagos**: persiste pedidos y avance de SAGA en MongoDB; coordina llamadas REST a Usuarios/Catálogo y simula el pago.
- **Aislamiento:** una instancia compartida de MongoDB con bases lógicas separadas por dominio. No hay transacción distribuida ACID entre Neo4j y MongoDB: las altas parciales deben detectarse y recuperarse.

## 4. Contratos JSON de referencia

**Usuario** y **pedido** preservan los campos del anexo (pág. 4). Los ejemplos de **producto** e **inventario** son propuestas del equipo, porque no aparecen definidos en ese anexo.

**Usuario — MongoDB (`usuarios`):**

```json
{"id":"usr_12345","tipo_documento":"DNI","nro_documento":"12345678","nombre":"Juan","apellido":"Pérez","email":"juan.perez@example.com","direcciones":[{"calle":"Av. Principal 123","ciudad":"Montevideo","codigo_postal":"11000"}]}
```

**Producto — respuesta REST, con relaciones en Neo4j:**

```json
{"id":"prod_001","nombre":"Auriculares Bluetooth","descripcion":"Auriculares inalámbricos","precio":25.50,"categoria_id":"cat_audio","marca_id":"marca_01","activo":true}
```

Modelar nodos `Producto`, `Categoria`, `Marca`; relaciones `PERTENECE_A`, `FABRICADO_POR` y `RELACIONADO_CON`. IDs únicos. La API expone IDs, pero las asociaciones se representan mediante **aristas**.

**Inventario — MongoDB (`inventario`), modelo propuesto por producto:**

```json
{"producto_id":"prod_001","disponible":10,"reservas":[{"reserva_id":"res_001","pedido_id":"ord_98765","cantidad":2,"estado":"ACTIVA"}]}
```

`disponible` **ya excluye** las unidades de reservas activas. Para el MVP se embeben las reservas en el documento del producto, permitiendo cambiar `disponible` y agregar/modificar una reserva **en una única escritura atómica**. Evitar duplicar `reserva_id`; considerar limpieza/archivo de reservas cerradas para que el documento no crezca indefinidamente.

**Pedido — MongoDB (`pedidos`):**

```json
{"pedido_id":"ord_98765","usuario_id":"usr_12345","estado":"PROCESANDO","items":[{"producto_id":"prod_001","cantidad":2,"precio_unitario":25.50}],"total":51.00,"pago":{"metodo":"TARJETA_CREDITO","estado_pago":"APROBADO","transaccion_id":"tx_456789"}}
```

Direcciones e ítems van **embebidos**; usuario/producto se unen por **referencia** (`usuario_id`, `producto_id`). Guardar precio histórico por ítem. El cliente **no decide** el precio ni el total: el backend los consulta/calcula. Usar centavos enteros o decimal exacto **internamente**, no `float` para calcular dinero.

## 5. API mínima y reglas transaccionales

| Servicio | Rutas |
|---|---|
| Usuarios | `POST /api/usuarios`; `GET /api/usuarios/{usuario_id}` |
| Catálogo | `POST /api/productos`; `GET /api/productos/{producto_id}` (incluye stock) |
| Pedidos | `POST /api/pedidos` (valida, inicia SAGA y retorna estado/ID) |
| Catálogo — internas | `POST /api/inventario/reservas`; `POST /api/inventario/reservas/{id}/confirmar`; `POST /api/inventario/reservas/{id}/liberar` |
| Para observar/demo | `GET /api/pedidos/{id}`; `GET /api/productos/{id}/relacionados`; `GET /api/productos` (si hace falta listar) |

**Chain of Responsibility (antes de los efectos):** `ValidarDatos` → `ValidarUsuario` → `ValidarProductosYCantidades` → `PrepararPedido`. La SAGA hace **reservas y pago**; evitar procesar pagos dos veces por mezclar patrones.

**SAGA orquestada:**

1. Crear pedido `PENDIENTE` + estado persistente de SAGA e identificador idempotente.
2. Reservar cada ítem en Catálogo/Inventario: actualización condicional sobre **un documento MongoDB** (`disponible >= cantidad`), restar cantidad y registrar la reserva en esa misma operación atómica.
3. Si algún ítem no tiene stock: **liberar las reservas anteriores** y marcar `RECHAZADO`.
4. Con todo reservado, **simular pago** configurable (`APROBADO`/`RECHAZADO`). Si falla: liberar reservas y marcar `CANCELADO`.
5. Si se aprueba: confirmar reservas y pedido `CONFIRMADO`.
6. Ante timeout/caída: persistir el último paso, **reintentar de modo idempotente** y reconciliar al reiniciar; si el pago fue aprobado pero falta confirmar, completar la confirmación o gestionar compensación explícita, **nunca asumir éxito sin verificar**.

**Invariantes:** no stock negativo; no doble reserva/liberación; no pedido duplicado al reintentar; pago simulado no se ejecuta dos veces para el mismo intento. En un pedido con múltiples productos, las reservas son **individuales**, no una operación atómica global: SAGA compensa las parciales. Definir un vencimiento y recuperación de reservas abandonadas **sin requerir otro contenedor** (p. ej. recuperación al arrancar y reconciliación periódica dentro del servicio).

## 6. Plan de acción para la IA desarrolladora

1. **Estructura e infraestructura:** crear `usuarios-service/`, `catalogo-service/`, `pedidos-service/`, `tests/`, `postman/`, `docs/`, `docker-compose.yml`, `.env.example` y README. Dockerfiles y healthchecks; esperar disponibilidad de MongoDB/Neo4j. **Cinco contenedores permanentes**.
2. **Persistencia y modelos:** Pydantic y validaciones; índices únicos (`usuario.id`, `usuario.email`, `producto.id`, `inventario.producto_id`, `pedido_id` y clave de idempotencia). Separar capas API/servicio/repositorio.
3. **CRUD requerido:** implementar endpoints de Usuarios y Catálogo; alta de producto coordinada entre Neo4j/MongoDB, recuperable si solo una escritura prospera. Agregar consulta de relaciones para demostrar Neo4j.
4. **Pedidos:** definir estados, Chain, orquestador SAGA, reservas condicionadas, pago simulado, confirmación, compensaciones, registro de progreso y reintentos.
5. **Pruebas:** generar `postman/ShopExpress.postman_collection.json` y `postman/local.postman_environment.json` (variables de URL/IDs; assertions); agregar Pytest/HTTPX para concurrencia, idempotencia y recuperación. Registrar evidencias reales de ejecución.
6. **Entrega:** README con decisiones, modelos, API, comandos y límites conocidos; diagramas Mermaid de **arquitectura**, **SAGA** y **Chain** en `docs/` o README. Preparar demo reproducible de unos 10 minutos.

**Estructura mínima:**

```text
shopexpress/
  usuarios-service/      # FastAPI + MongoDB
  catalogo-service/      # FastAPI + Neo4j + MongoDB
  pedidos-service/       # FastAPI + MongoDB + SAGA/Chain
  tests/                 # Pytest / HTTPX
  postman/               # Colección + entorno local
  docs/                  # Diagramas y decisiones
  docker-compose.yml
  .env.example
  README.md
```

**Comandos que deberá documentar y hacer funcionar la IA:**

```bash
docker compose up --build -d
docker compose ps
postman collection run postman/ShopExpress.postman_collection.json -e postman/local.postman_environment.json
pytest -q
docker compose down
```

Postman CLI y Pytest se ejecutan **fuera de Docker**; si falta alguna dependencia, documentar su instalación. Swagger UI de cada FastAPI estará disponible en `/docs`.

## 7. Aceptación y defensa

- [ ] Crear y consultar usuarios/productos; consultar el stock y **una relación real** de Neo4j.
- [ ] Pedido correcto: stock reservado, pago aprobado y pedido confirmado.
- [ ] Sin stock: rechazo sin descontar inventario.
- [ ] Pago rechazado: liberar reservas y cancelar pedido.
- [ ] Dos compras simultáneas por **una última unidad**: solo una gana; nunca hay stock negativo.
- [ ] Reintentos / timeout: no duplican pedidos, reservas ni pagos; recuperación de SAGA verificada.
- [ ] Comandos de Docker + colección Postman + Pytest ejecutados con resultado documentado.
- [ ] README, **tres diagramas**, código y pruebas en un solo repositorio Git.

**Fuera de alcance por decisión:** frontend/back-office, autenticación completa, pagos reales, carrito persistente, Kafka, API Gateway, Kubernetes y despliegue productivo. **Opcional:** exportación anonimizada y una mención conceptual a CQRS/Event Sourcing/privacidad.

## 8. Instrucción de traspaso a otra IA

> Implementá ShopExpress siguiendo **este plan y la consigna original**, por etapas y conservando la arquitectura acordada: **3 FastAPI + MongoDB + Neo4j = 5 contenedores**, sin frontend. Prioridad: **correctitud transaccional y prueba de no sobreventa**, antes de extras. Usá los JSON del anexo como contratos base, y marcá las extensiones propuestas. Entregá código ejecutable, Compose, pruebas Postman/Pytest y README/diagramas; no declares pruebas exitosas sin ejecutarlas. Documentá cualquier cambio respecto de estas decisiones y su justificación. Empezá por infraestructura/modelos, después CRUD, SAGA/Chain, pruebas y documentación.

**Referencia documental:** consigna *“Tarea 2 - 2026: Diseño de un Sistema de Microservicios para una Plataforma de Comercio Electrónico”*, pp. 1–4; anexo JSON en p. 4. Referencia operativa de Postman CLI: <https://learning.postman.com/docs/postman-cli/postman-cli-collections>.
