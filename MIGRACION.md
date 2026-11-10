# Biblioteca: migración a tres servicios

> Migración de este workspace completada el **10/11/2026**. Para operar el sistema activo, ver [MIGRACION_REAL.md](MIGRACION_REAL.md). Las fases siguientes son el procedimiento para una instalación nueva; no deben repetirse sobre los destinos ya importados.

Implementación: 09/11/2026. La transferencia de datos reales y el cambio de tráfico son operaciones explícitas; no se ejecutan al arrancar los contenedores nuevos.

## Componentes

| Componente | Responsabilidad | Datos |
| --- | --- | --- |
| svc-identidad:8001 | Login/logout, usuarios, alumnos, administradores, perfil | identidad_db |
| svc-libros:8003 | Bibliografía, inventario, reservas, bajas | libros_db |
| svc-prestamos:8004 | Solicitud, aprobación, devolución, multas, RN-04, Saga | prestamos_db |
| nginx:8080 | Rutas públicas y bloqueo de /internal/ | Sin BD |
| RabbitMQ | Comandos/eventos durables y reintentos | Volumen rabbit_data |

Solo el dueño escribe su contexto. Catálogo no consulta tablas de préstamos; identidad compone resúmenes mediante HTTP por lotes. Cada servicio valida tokens contra identidad, con una clave interna, sin almacenar contraseñas ajenas. La BD heredada es una proyección temporal durante la extracción.

Los directorios `svc-auth` y `svc-usuarios` son borradores históricos, excluidos de Compose. El código nuevo vive en `services/svc-identidad`, `services/svc-libros`, `services/svc-prestamos`; `services/common` contiene infraestructura, nunca modelos ORM de dominio compartidos. Outbox, inbox y mensajes fallidos pertenecen a la BD de cada participante.

GCS sigue en el monolito: no existe un campo/endpoint de archivos de libros que permita verificar su traslado. No se añade un subsistema de archivos ficticio al catálogo.

## Preparación y arranque

Usa Docker Desktop y Compose >=2.24.4. Conserva el `.env` existente; agrega las claves nuevas de `.env.example` con valores propios. Las contraseñas de AMQP deben ser URL-safe. En este workspace ya se generaron las claves faltantes sin reemplazar credenciales anteriores.

```sh
docker compose config --quiet
docker compose up --build -d
```

El arranque por defecto conserva TODOS los contextos en `web:8000`; no dirige usuarios a bases nuevas vacías. Los servicios nuevos ejecutan sus migraciones, pero no importan ni sobrescriben datos de dominio. Angular usa `src/app/api.config.ts`, con gateway `http://localhost:8080`.

Antes de cada transferencia: poner `MAINTENANCE_MODE=1` en `.env` y recrear nginx (`docker compose up -d --force-recreate nginx`) para bloquear POST/PUT/PATCH/DELETE con 503, detener consumidores/escritores del contexto, tomar respaldo nativo de MySQL y exportar un snapshot. Una pausa debe incluir pagos y devoluciones. Después de conciliar, volver a `MAINTENANCE_MODE=0`, recrear nginx y validar el flujo antes de dar por completada la fase. No usar `test_reglas_devolucion.py` como chequeo: modifica la BD real.

## 1. Transferir identidad

Con escrituras pausadas y el monolito aún como fuente:

```sh
docker compose exec web python manage.py export_migration --output /app/exports/identidad.json
docker compose cp web:/app/exports/identidad.json ./exports/identidad.json
docker compose cp ./exports/identidad.json svc-identidad:/tmp/identidad.json
docker compose exec svc-identidad python manage.py import_snapshot /tmp/identidad.json
docker compose exec svc-identidad python manage.py import_snapshot /tmp/identidad.json --verify-only
```

El snapshot incluye hashes y tokens: está excluido de Git e imágenes y se crea con permisos 0600. La importación valida checksum, referencias, IDs, todos los campos exportados aplicables, grupos y conteos; rechaza destinos no vacíos. No cambia contraseñas a texto plano ni reasigna IDs.

Cambiar en `.env` y recrear `web`/nginx:

```dotenv
IDENTITY_UPSTREAM=svc-identidad:8001
IDENTITY_AUTH_ENABLED=1
LOANS_OWNER_URL=http://web:8000
```

```sh
docker compose up -d --force-recreate web nginx
```

Validar registro nuevo, login existente y nuevo, perfil, cambio de contraseña, bloqueo y desactivación antes de reabrir escrituras. El monolito valida tokens remotamente y crea proyecciones de perfiles al recibir solicitudes; dichas proyecciones tienen contraseñas inutilizables.

## 2. Transferir catálogo

Pausar escrituras de catálogo Y préstamos. Exportar un snapshot actualizado y repetir los comandos anteriores con `catalogo.json` y `svc-libros`. El importador de catálogo crea reservas confirmadas para préstamos activos; sus IDs de Saga son deterministas. Rechaza stock menor a los préstamos existentes o libros dados de baja con préstamos activos.

```dotenv
BOOKS_UPSTREAM=svc-libros:8003
CATALOG_REMOTE_ENABLED=1
```

```sh
docker compose up -d --force-recreate web worker-legacy nginx
```

Mientras préstamos siga en el monolito, sus acciones usan comandos internos idempotentes del catálogo. No actualizan la disponibilidad del dueño remoto mediante un contador local. Las filas de libros heredadas son proyecciones bibliográficas para conservar FKs hasta extraer préstamos. `worker-legacy` consulta las asignaciones remotas y recupera aprobaciones interrumpidas; un timeout no libera stock automáticamente. Un administrador puede rechazar una aprobación pendiente para liberar su reserva.

Antes de continuar, verificar que no quedan reservas pendientes de aprobaciones interrumpidas. Para diagnóstico:

```sh
docker compose exec web python manage.py recover_catalog
```

## 3. Transferir préstamos y activar Saga

Pausar solicitudes, aprobaciones, devoluciones y pagos; detener `worker-legacy` DESPUÉS de drenar sus operaciones. Exportar `prestamos.json` actualizado e importarlo/verificarlo en `svc-prestamos`. No volver a importar identidad ni catálogo: ya son sus propias fuentes de verdad.

La importación conserva historial, fechas, multas pagadas, IDs de alumno/libro y los IDs deterministas de asignaciones activas. Antes de cambiar tráfico, ejecutar `docker compose exec svc-prestamos python manage.py reconcile_dependencies` para comprobar referencias en identidad/catálogo y coincidencia exacta entre reservas y préstamos activos. Resolver cualquier diferencia. No continuar si hay Sagas heredadas sin resolver.

```dotenv
LOANS_UPSTREAM=svc-prestamos:8004
LOANS_OWNER_URL=http://svc-prestamos:8004
CATALOG_REMOTE_ENABLED=0
```

```sh
docker compose stop worker-legacy
docker compose up -d --force-recreate svc-identidad svc-libros svc-prestamos worker-libros worker-prestamos nginx
```

Validar el flujo completo y reabrir escrituras. Aprobar/devolver responden 202; Angular espera `/operaciones/<uuid>/`, muestra el resultado confirmado y guarda operaciones pendientes para recuperarlas al abrir el panel. Los estados de negocio siguen siendo pendiente/aceptado/rechazado; el progreso técnico vive en Saga.

## 4. Retirar el monolito

Después de conciliar y pasar los escenarios de aceptación:

```sh
docker compose stop web worker-legacy db
docker compose -f docker-compose.yml -f docker-compose.final.yml up -d
```

La configuración final no arranca el monolito ni tiene rutas hacia él. Sus fuentes y volúmenes se conservan para auditoría/reversión. No usar `down -v`: destruiría los datos.

**Reversión:** antes de aceptar escrituras nuevas puede restituirse el destino anterior. Después, congelar escrituras, exportar los datos del dueño nuevo y conciliar cambios antes de restaurar rutas. El snapshot inicial no contiene registros posteriores. Mantener respaldos nativos de cada BD y del broker; no presentar un simple cambio de nginx como reversión completa.

## Pruebas

Resultados ejecutados y límites: [VALIDACION.md](VALIDACION.md).

Aisladas (SQLite; no prueban bloqueos MySQL):

```sh
SQLITE_TEST=1 python3 services/svc-identidad/manage.py test identidad
SQLITE_TEST=1 python3 services/svc-libros/manage.py test catalogo
SQLITE_TEST=1 python3 services/svc-prestamos/manage.py test circulacion
PYTHONPATH=services/common SQLITE_TEST=1 python3 manage.py test biblioteca_backend.migration_tests --settings=biblioteca_backend.test_settings
```

Estas pruebas cubren RN-03/RN-04, reintentos, compensación, mensajes tardíos, permisos e importación/conciliación. Nunca ejecutan el script heredado que siembra datos reales.

Integración real, en un proyecto Docker separado, con puerto 18080 y credenciales solo de prueba:

```sh
python3 tests/prepare_compose.py
docker compose -p biblioteca-verificacion -f /tmp/biblioteca-integration-compose.json up --build -d --scale worker-libros=2 --scale worker-prestamos=2
docker compose -p biblioteca-verificacion -f /tmp/biblioteca-integration-compose.json exec svc-identidad python manage.py createsuperuser --username integration-admin --email integration-admin@example.com
# Para esta suite aislada usar IntegrationPassword123 como contraseña del administrador.
docker compose -p biblioteca-verificacion -f /tmp/biblioteca-integration-compose.json cp tests/e2e.py svc-prestamos:/tmp/e2e.py
docker compose -p biblioteca-verificacion -f /tmp/biblioteca-integration-compose.json exec svc-prestamos python /tmp/e2e.py
```

La suite real verifica flujo completo, pago idempotente, permisos, competencia por la última copia y cuatro aprobaciones concurrentes para un alumno. El generador excluye las bases y el monolito originales y reemplaza credenciales en memoria; los volúmenes usan el proyecto `biblioteca-verificacion`.

Para recuperación: copiar `tests/fault_scenarios.py` al contenedor, detener `rabbitmq` (o `worker-prestamos`) en ese proyecto, ejecutar `python /tmp/fault_scenarios.py start`, iniciar el componente y ejecutar `python /tmp/fault_scenarios.py finish`. Verifica operación pendiente durable, recuperación, duplicados reales y comandos tardíos después de devolver. Detener los contenedores de verificación al terminar; sus volúmenes se conservan.

Frontend: `npm run build -- --configuration development` desde el repositorio Angular.

## Operación

- `GET /health/` comprueba proceso y BD; no afirma que todas las dependencias estén disponibles.
- `GET /internal/metrics/` con clave de servicio muestra outbox pendiente, antigüedad, mensajes fallidos y Sagas pendientes. Consultarlo dentro de la red Docker.
- `docker compose logs worker-libros worker-prestamos` contiene `saga_id`, tipo e identificador del mensaje.
- RabbitMQ management está ligado a `127.0.0.1:15672`. Revisar colas `catalogo.failed` y `circulacion.failed`.
- Corregir la causa y ejecutar `docker compose exec svc-prestamos python manage.py replay_failed <message_id>` (o `svc-libros`). El reproceso usa outbox y el ID original para deduplicar. El registro de la cola de fallos se conserva para auditoría.
- Las fallas persistentes conservan reservas/cupos hasta recuperación o compensación explícita; las métricas y la cola de fallos deben revisarse durante la demostración.
