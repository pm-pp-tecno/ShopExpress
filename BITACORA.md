# Bitácora de decisiones — ShopExpress

El plan vigente es `PLAN_DESARROLLO_SHOPEXPRESS.md`. Acá queda quién aportó cada tramo y qué se cambió.

## Gabriel

Commit `ab22f33` (*Markdown con proceso del desarrollo, arquitectura adoptada y plan de acción*).

Dejó el plan de implementación: tres servicios FastAPI, MongoDB y Neo4j, cinco contenedores, sin frontend. Neo4j modela el catálogo (producto, categoría, marca y productos relacionados). El stock vive en MongoDB y se reserva con una escritura atómica por producto. La cadena de responsabilidad solo valida, antes de tocar datos. La SAGA, dentro de Pedidos, reserva, cobra, confirma y compensa. Las pruebas cubren el pedido correcto, el rechazo de pago y dos compras a la vez por la última unidad.

## Pablo

Revisión del 29/10/2026 sobre ese plan.

Antes de adoptar el plan de Gabriel se había pensado Redis para el stock, y después Neo4j también para el stock. Esas dos variantes se descartaron: el corte de Gabriel usa cada base para lo que la consigna pide mostrar.

Sobre el plan de Gabriel quedaron estos ajustes:

- `GET /api/usuarios/{usuario_id}` muestra el historial pidiéndoselo a Pedidos. No se guarda una copia en el usuario.
- Confirmar una reserva solo cambia su estado a `CONFIRMADA`. El stock ya se descontó al reservar.
- Si Pedidos se cae a mitad de una SAGA, la retoma al arrancar. No hay un proceso periódico aparte.
- El precio y el total los calcula el backend con decimal exacto. La respuesta sigue la forma del anexo.

La SAGA no es un servicio ni un contenedor: es el código de Pedidos que encadena esas llamadas y deshace las que ya confirmaron.
