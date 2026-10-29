# Diagramas

## Arquitectura

```mermaid
flowchart LR
  Cliente[Postman_o_Swagger]
  Usuarios[Usuarios_8001]
  Catalogo[Catalogo_8002]
  Pedidos[Pedidos_8003]
  Mongo[(MongoDB)]
  Neo4j[(Neo4j)]

  Cliente --> Usuarios
  Cliente --> Catalogo
  Cliente --> Pedidos
  Pedidos -->|validar_usuario| Usuarios
  Usuarios -->|historial| Pedidos
  Pedidos -->|reservar_confirmar_liberar| Catalogo
  Usuarios --> Mongo
  Catalogo --> Neo4j
  Catalogo --> Mongo
  Pedidos --> Mongo
```

## Chain of Responsibility

Corre dentro de Pedidos, antes de escribir el pedido.

```mermaid
flowchart TD
  post[POST_api_pedidos]
  datos[ValidarDatos]
  usuario[ValidarUsuario]
  productos[ValidarProductosYCantidades]
  preparar[PrepararPedido]
  saga[SAGA]
  post --> datos --> usuario --> productos --> preparar --> saga
```

## SAGA

También corre dentro de Pedidos. Cada reserva es atómica en su documento de MongoDB. Si una falla, se liberan las anteriores.

```mermaid
flowchart TD
  crear[Crear pedido PENDIENTE]
  reservar[Reservar cada item]
  stock{Hay stock}
  liberarStock[Liberar reservas hechas]
  rechazado[Estado RECHAZADO]
  pagar[Simular pago]
  pago{Pago aprobado}
  liberarPago[Liberar reservas]
  cancelado[Estado CANCELADO]
  confirmar[Confirmar reservas sin restar stock]
  ok[Estado CONFIRMADO]
  crear --> reservar --> stock
  stock -->|no| liberarStock --> rechazado
  stock -->|si| pagar --> pago
  pago -->|no| liberarPago --> cancelado
  pago -->|si| confirmar --> ok
```
