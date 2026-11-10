# Validación — 09/11/2026

> Registro histórico de validación previa a la migración. Los límites sobre bases originales y navegador que aparecen abajo quedaron superados el **10/11/2026**; el resultado real vigente está en [MIGRACION_REAL.md](MIGRACION_REAL.md).

## Resultados

| Comprobación | Resultado |
| --- | --- |
| Identidad: autenticación, permisos, composición e importación | 7 pruebas correctas |
| Catálogo: stock, idempotencia, liberación terminal e importación | 9 pruebas correctas |
| Préstamos: Saga, reglas, permisos, transporte e importación | 16 pruebas correctas |
| Monolito: adaptadores, exportación y validación de solicitudes | 5 pruebas correctas |
| Integración HTTP/nginx/MySQL/RabbitMQ | 4 escenarios correctos |
| Broker detenido → operación pendiente → reinicio | Correcto |
| Workers detenidos antes de publicar → reinicio | Correcto |
| Duplicados reales y comandos tardíos tras devolución | Correcto |
| Angular: compilación de desarrollo | Correcta |
| Compose inicial/final y contratos JSON | Válidos |

Los servicios nuevos se probaron con Django 5.0.2 y DRF 3.15.2 de sus imágenes. Los adaptadores también se probaron con Django 5.0.2 y DRF 3.14.0 del monolito; los últimos ajustes de presentación de devoluciones se comprobaron además con su suite local. Las pruebas aisladas usan BD efímera SQLite; la concurrencia se comprobó por HTTP con MySQL 8, RabbitMQ, dos workers por participante y varios procesos/hilos de Gunicorn.

La integración cubrió registro, login, perfil, solicitud, aprobación asíncrona, devolución, multa de 50 MXN por diez días, pago idempotente y persistencia del bloqueo RN-04. Dos aprobaciones sobre la última copia produjeron una asignación. Cuatro aprobaciones concurrentes de un alumno ocuparon tres cupos y rechazaron la cuarta.

Durante la recreación de servicios se detectó que nginx retenía direcciones IP antiguas. Se cambió a resolución DNS dinámica de Docker y se repitió satisfactoriamente la integración.

## Límites

- No se importaron ni modificaron las bases originales; se usó el proyecto `biblioteca-verificacion`, con bases, credenciales, volúmenes y red propios.
- No se cambió el tráfico real al nuevo sistema. Compose conserva el monolito por defecto hasta importar y conciliar cada contexto.
- Los importadores se probaron con snapshots sintéticos, checksum, verificación de campos y rechazo de sobrescrituras. La conciliación de datos reales debe ejecutarse durante el procedimiento de MIGRACION.md.
- No se hizo una prueba de navegador con interacción visual; se compiló Angular y se verificaron los contratos HTTP que consume.
- GCS permanece en el código heredado: no se identificó una función de archivos de libros conectada al catálogo que pudiera migrarse y probarse.
