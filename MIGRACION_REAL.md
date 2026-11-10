# Migración real completada — 10/11/2026

Estado: **activa**. Confirmación final: `2026-11-10T12:27:40-06:00`.

- Página: http://localhost:4200/catalogo
- API Gateway: http://localhost:8080
- Arquitectura activa: identidad (8001), catálogo (8003), préstamos (8004), MySQL independiente y Saga con RabbitMQ.
- Mantenimiento: desactivado. El monolito y worker-legacy no sirven tráfico.

## Datos conservados

| Entidad | Fuente | Destino |
| --- | ---: | ---: |
| Usuarios | 5 | 5 |
| Alumnos | 3 | 3 |
| Administradores | 2 | 2 |
| Libros | 25 | 25 |
| Préstamos | 8 | 8 |
| Tokens | 5 | 5 |

Al abrir el sistema se conservaron seis solicitudes pendientes, un préstamo activo y uno devuelto. No se aprobaron solicitudes, registraron devoluciones ni pagaron multas en los datos reales para probar la migración.

Los tres servicios se importaron desde **el mismo snapshot**. La verificación comprobó IDs, hashes de contraseñas, tokens, grupos, timestamps con seis microsegundos decimales, campos, referencias y conteos. La asignación confirmada del catálogo coincide exactamente con el préstamo activo.

## Respaldo y auditoría

Carpeta privada: `backups/20261110-081308/`, excluida de Git, permisos de directorio 0700 y archivos sensibles 0600.

- `biblioteca1_db.sql`: respaldo nativo con esquema, datos, triggers, rutinas y eventos.
- `snapshot.json`: transferencia única de datos.
- `baseline.json`: comparación de multas, pagos y bloqueos al mismo instante UTC.
- `manifest.json`: estados y evidencias de la operación.
- `.env` y archivos Compose/nginx: configuración previa al cambio.
- `procedimiento/`: scripts ejecutados para auditoría; sus comprobaciones de fase impiden reiniciar la migración por accidente.

SHA-256 del respaldo nativo:

`b5532556eed006960889f481e0f3b3e8b902eb6502a9c6b5ab68c46837f680cc`

SHA-256 del contenido canónico del snapshot:

`0e10ee06ff29443a3d916d01728f648fed4e3b02c3f9a2d19231495b965b8cfe`

El respaldo nativo se restauró en una base aislada: los conteos y checksums de **todas las tablas** coincidieron con la fuente. Antes de archivar el original se repitió la comprobación y seguía intacto. No se eliminó ningún volumen.

## Conciliación y pruebas

- Multas, pagos, sanciones y estados de bloqueo coinciden con el monolito en `2026-11-10T15:00:54.387477+00:00`.
- Se corrigió el exportador: Django truncaba fechas a milisegundos; ahora se preservan los microsegundos completos.
- Se preservó el calendario **UTC heredado** de RN-03/RN-04. Usar días de México alteraba una multa en 5 MXN; se detectó antes de abrir el sistema, se corrigió el cálculo y se añadió una prueba de regresión. No se alteraron fechas ni importes guardados.
- El bloqueo por un préstamo aún sin devolver no anuncia una fecha de desbloqueo provisional: conserva el estado bloqueado hasta devolver y cumplir la suspensión correspondiente.
- Las cinco sesiones existentes pasaron por el gateway: perfil y visibilidad de préstamos correctos; alumnos sin acceso a gestión de usuarios; administradores con acceso permitido.
- Catálogo visible en navegador con sus 25 libros; CORS permite el frontend 4200 y no quedan URLs del backend 8000 en Angular.
- Antes de abrir: cero Sagas pendientes, cero outbox pendiente y cero mensajes fallidos.
- Cuatro pruebas E2E con escrituras y concurrencia pasaron sobre una **copia aislada del snapshot real**, proyecto `biblioteca-migracion-ensayo-20261110-081308`, sin usar los volúmenes de biblioteca-verificacion. Sus contenedores se detuvieron y sus volúmenes se conservaron.

## Operación habitual

Desde `biblioteca_backend/`:

```sh
docker compose up -d
```

El `.env` local fija `COMPOSE_FILE=docker-compose.yml:docker-compose.final.yml`, los destinos definitivos y `MAINTENANCE_MODE=0`. También puede usarse `scripts/arrancar_microservicios.sh`. No ejecutar el perfil legacy para el funcionamiento habitual.

Desde `biblioteca-webapp/`, si el frontend estuviera detenido:

```sh
npm start -- --host localhost --port 4200
```

La instancia del frontend de Trabajo Colaborativo que ocupaba 4200 se detuvo con autorización expresa. Su API en 8000 y su base de datos en 3306 siguen intactas y en ejecución.

## Fuente archivada y reversión

El contenedor `biblioteca_db` y su volumen `biblioteca_backend_mysql_data` se conservaron y quedaron detenidos. La copia nativa restaurada de auditoría también se conservó detenida. La fuente se protegió contra escrituras antes del respaldo; sus valores anteriores están en el manifiesto privado.

Después de abrir el sistema, los cambios nuevos pertenecen a los microservicios. Para revertir: activar mantenimiento, drenar o compensar operaciones, respaldar los tres destinos y RabbitMQ, conciliar las escrituras posteriores al corte y solo entonces restaurar servicio en el monolito. No basta con cambiar las rutas ni restaurar el snapshot inicial. No utilizar `docker compose down -v`.
