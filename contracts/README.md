# Contratos

- `openapi.json`: API pública v1. Se conservan `/token/`, `/custom-token/`, `/alumnos/`, `/register/`, `/perfil/`, `/usuarios/`, `/libros/`, `/prestamos/`, `/solicitar-prestamo/` y las acciones antiguas.
- `events.schema.json`: envelope v1 de comandos/eventos. Exchange topic durable `biblioteca.v1`; routing `catalogo.<comando>` y `circulacion.<evento>`. Colas `catalogo`, `circulacion`, sus colas de reintentos y `.failed`.
- `GET /internal/validate/` en identidad: exige `X-Service-Key` y `Authorization: Token ...`; devuelve `id`/`user_id`, `alumno_id`, `admin_id`, `rol`, `is_active`, `is_superuser` y datos básicos del perfil. Los servicios construyen un principal sin ORM User local.
- `POST /internal/alumnos/` en identidad: `{alumno_ids:[int64]}` → objeto por ID, máximo 1000 IDs. `GET /internal/usuarios/<user_id>/` devuelve perfil básico sin consultar préstamos.
- `POST /internal/libros/` en catálogo: `{libro_ids:[int64]}` → objeto por ID, incluyendo disponibilidad. No consulta préstamos.
- `POST /internal/resumenes/` en el dueño de préstamos: `{alumno_ids:[int64]}` → objeto por alumno con bloqueo, multas, sanciones e historial. La identidad consume lotes y falla con 503 si no puede enriquecerlos.
- `POST /internal/historial/`: `{alumno_id:int64}` → lista de préstamos para recomendaciones.
- `POST /internal/pagar-multa/`: `{alumno_id:int64, prestamo_id?:int64}` → pago solo de multas devueltas no pagadas. Un reintento no vuelve a cobrar.
- Todos los endpoints internos exigen la clave de servicio; nginx devuelve 404 y elimina credenciales internas enviadas por clientes públicos.
- `POST /internal/legacy-reserva/` y `GET /internal/legacy-reservas/` son adaptadores temporales de catálogo para la fase previa a extraer préstamos. Desactivarlos al retirar el monolito.

## Semántica asíncrona

Aprobar/devolver devuelven 202 con `operacion_id`. Consultar `/operaciones/<id>/` hasta `completada` o `fallida`. `resultado` contiene el mensaje y, al devolver, `detalles_devolucion`. Un rechazo pendiente sin Saga devuelve 200; si requiere compensación devuelve 202 y acaba `fallida` con su motivo de rechazo y `resultado.rechazo_confirmado=true`, que la interfaz trata como rechazo confirmado.

La aprobación ocupa un cupo del alumno mientras está reservando/confirmando/compensando. Catálogo ocupa un ejemplar mientras está reservado/confirmado. Solo `ReservaConfirmada` permite aceptar el préstamo e iniciar los siete días.

La liberación conserva una reserva terminal por préstamo, incluso si llegó antes que la reserva. `reserva_saga_id` identifica la asignación original; `saga_id` correlaciona la operación actual (incluida la devolución). Una liberación no se revierte con comandos tardíos. Un préstamo rechazado requiere una solicitud nueva para volver a intentarse.

La entrega es al menos una vez. Inbox deduplica por mensaje; las transiciones también son idempotentes ante IDs nuevos. Outbox y efectos del dominio se confirman juntos. Cinco reintentos de consumo (2, 4, 8, 16 y 30 segundos) preceden la cola de fallos. El publicador reintenta indefinidamente si el broker está caído. Las Sagas sin progreso se reemiten cada 60 segundos, conservando sus IDs y cupos.

Una Saga que falla permanentemente por infraestructura conserva su reserva/cupo y queda visible hasta corregir la causa y reprocesar. No se libera stock por suponer que un timeout significa fallo.

## Calendario de penalizaciones

RN-03 y RN-04 calculan días con el calendario UTC heredado del monolito. La presentación en América/México no debe cambiar días de retraso, multas ni elegibilidad de datos importados. Los timestamps se transfieren con seis dígitos de microsegundos.
