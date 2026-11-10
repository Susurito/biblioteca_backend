> **Actualización 09/11/2026:** este reporte conserva el trabajo histórico. Las fases marcadas completadas abajo no prueban interoperabilidad entre bases independientes. La arquitectura vigente es de tres servicios; el estado de implementación y la validación están en [MIGRACION.md](MIGRACION.md). La afirmación histórica de compatibilidad por compartir `SECRET_KEY` no aplica a tokens DRF.

# 📋 Reporte de Migración a Microservicios — Biblioteca Backend

Este documento registra de manera incremental los cambios, refactorizaciones y avances realizados durante cada fase de la migración del sistema monolítico hacia una arquitectura de microservicios orientada por el patrón **Strangler Fig**.

---

## 📌 Resumen General del Roadmap

| Fase | Descripción | Estado | Fecha de Finalización |
| :--- | :--- | :---: | :---: |
| **Fase 0** | Preparación, limpieza técnica y consolidación de serializers | 🟢 Completada | 31/10/2026 |
| **Fase 1** | Extracción de `svc-auth` + API Gateway (Nginx) | 🟢 Completada | 31/10/2026 |
| **Fase 2** | Extracción de `svc-usuarios` (Alumnos, Administradores) | 🔵 Pendiente | — |
| **Fase 3** | Extracción de `svc-libros` (Catálogo + GCS) | 🔵 Pendiente | — |
| **Fase 4** | Extracción de `svc-prestamos` (Reglas de negocio + Saga/Eventos) | 🔵 Pendiente | — |
| **Fase 5** | Desmantelamiento y retiro del monolito original | 🔵 Pendiente | — |

---

## 🟢 Fase 0: Preparación, Limpieza y Consolidación

### 🎯 Objetivo
Reducir deuda técnica, eliminar código muerto y unificar fuentes de verdad en el monolito Django existente para preparar una base de código limpia y desacoplada antes de iniciar la extracción de servicios.

### 📊 Métricas de Código (Líneas de Código)

| Archivo | Líneas Antes | Líneas Después | Diferencia | Impacto Principal |
| :--- | :---: | :---: | :---: | :--- |
| [`views/views.py`](file:///Users/susurito/Desktop/2026/Buap/Arquitectura%20de%20software/biblioteca_backend/biblioteca_backend/views/views.py) | 835 | 662 | **-173** | Eliminación de serializers duplicados y prints de debug |
| [`views/alumnos.py`](file:///Users/susurito/Desktop/2026/Buap/Arquitectura%20de%20software/biblioteca_backend/biblioteca_backend/views/alumnos.py) | 127 | 86 | **-41** | Eliminación de bloques grandes comentados |
| [`views/auth.py`](file:///Users/susurito/Desktop/2026/Buap/Arquitectura%20de%20software/biblioteca_backend/biblioteca_backend/views/auth.py) | 142 | 115 | **-27** | Limpieza de código obsoleto de desarrollo |
| [`serializers.py`](file:///Users/susurito/Desktop/2026/Buap/Arquitectura%20de%20software/biblioteca_backend/biblioteca_backend/serializers.py) | 155 | 183 | **+28** | Centralización de lógica y campos de bloqueo |
| **Total Neto** | **1,259** | **1,046** | **-213** | **Reducción del 16.9% de código redundante** |

---

### 🛠️ Detalle de Cambios por Componente

#### 1. [`biblioteca_backend/serializers.py`](file:///Users/susurito/Desktop/2026/Buap/Arquitectura%20de%20software/biblioteca_backend/biblioteca_backend/serializers.py)
- **Única Fuente de Verdad:** Se consolidaron aquí todas las clases `UserSerializer`, `AdminSerializer`, `AlumnoSerializer`, `LibrosSerializer` y `PrestamosSerializer`.
- **Campos de Bloqueo Integrados:** Se incorporaron los campos dinámicos `alumno_bloqueado` y `motivo_bloqueo` en `PrestamosSerializer` con sus respectivos métodos de cálculo (`get_alumno_bloqueado`, `get_motivo_bloqueo`).
- **Resolución de Dependencias:** Se reorganizaron los imports al inicio y se implementaron imports diferidos (*lazy imports*) para resolver importaciones circulares entre modelos y vistas.

#### 2. [`biblioteca_backend/views/views.py`](file:///Users/susurito/Desktop/2026/Buap/Arquitectura%20de%20software/biblioteca_backend/biblioteca_backend/views/views.py)
- **Eliminación de Redundancia:** Se removieron las definiciones duplicadas de serializers que coexistían con `serializers.py`.
- **Limpieza de Consola:** Se eliminaron llamadas directas `print(...)` de depuración en rutas de préstamos y libros, mejorando el rendimiento y la limpieza de logs en producción.
- **Importación Limpia:** Ahora consume directamente los serializers centralizados desde `biblioteca_backend.serializers`.

#### 3. [`biblioteca_backend/views/alumnos.py`](file:///Users/susurito/Desktop/2026/Buap/Arquitectura%20de%20software/biblioteca_backend/biblioteca_backend/views/alumnos.py)
- Se eliminaron comentarios multilínea que contenían versiones antiguas del flujo de creación y asignación de usuarios y grupos.

#### 4. [`biblioteca_backend/views/auth.py`](file:///Users/susurito/Desktop/2026/Buap/Arquitectura%20de%20software/biblioteca_backend/biblioteca_backend/views/auth.py)
- Se removió un bloque comentado de lógica de desarrollo (`test_passwords`) para verificar credenciales de prueba, manteniendo solo el flujo estándar de autenticación por Token de Django Rest Framework.

#### 5. [`biblioteca_backend/views/__init__.py`](file:///Users/susurito/Desktop/2026/Buap/Arquitectura%20de%20software/biblioteca_backend/biblioteca_backend/views/__init__.py)
- Se actualizaron las re-exportaciones del paquete `views` para que los serializers se expongan desde `serializers.py` en vez de referenciar `views.py`.

---

### 🧪 Verificación y Pruebas del Sistema

Se ejecutó la verificación de integridad de Django en el entorno de contenedores:

```bash
docker-compose exec web python manage.py check
```

**Resultado:**
```text
System check identified no issues (0 silenced).
```
El sistema arrancó y validó modelos, rutas y serializers sin advertencias ni errores de sintaxis o dependencias rotas.

---

## 🟢 Fase 1: Extracción de `svc-auth` + API Gateway (Nginx)

### 🎯 Objetivo
Extraer la lógica de autenticación del monolito a su propio microservicio independiente (`svc-auth`), sin romper la funcionalidad existente. Introducir **Nginx como API Gateway** para enrutar el tráfico hacia el servicio correcto. El monolito sigue activo y sirve todo lo demás.

### 🏗️ Arquitectura resultante (Fase 1)

```
                    ┌─────────────────────┐
Cliente/Frontend    │   nginx :8080       │  ← Único punto de entrada
                    │   (API Gateway)     │
                    └──────┬──────────────┘
                           │
              ┌────────────┴────────────┐
              │                         │
    /token/   │                         │  /libros/, /prestamos/
    /logout/  ▼                         ▼  /alumnos/, etc.
    /validate/ svc-auth :8001      web (monolito) :8000
              │                         │
              ▼                         ▼
          db-auth (MySQL)           db (MySQL)
          auth_db                   biblioteca1_db
```

---

### 📁 Archivos Creados

| Archivo | Descripción |
| :--- | :--- |
| [`services/svc-auth/Dockerfile`](file:///Users/susurito/Desktop/2026/Buap/Arquitectura%20de%20software/biblioteca_backend/services/svc-auth/Dockerfile) | Imagen Python 3.11-slim con cliente MySQL |
| [`services/svc-auth/requirements.txt`](file:///Users/susurito/Desktop/2026/Buap/Arquitectura%20de%20software/biblioteca_backend/services/svc-auth/requirements.txt) | Dependencias mínimas: Django, DRF, simplejwt, mysqlclient, requests |
| [`services/svc-auth/manage.py`](file:///Users/susurito/Desktop/2026/Buap/Arquitectura%20de%20software/biblioteca_backend/services/svc-auth/manage.py) | Entry-point CLI de Django |
| [`services/svc-auth/auth_service/settings.py`](file:///Users/susurito/Desktop/2026/Buap/Arquitectura%20de%20software/biblioteca_backend/services/svc-auth/auth_service/settings.py) | Configuración mínima: sin admin, sin sesiones, misma `SECRET_KEY` del monolito |
| [`services/svc-auth/auth_service/urls.py`](file:///Users/susurito/Desktop/2026/Buap/Arquitectura%20de%20software/biblioteca_backend/services/svc-auth/auth_service/urls.py) | Rutas: `/token/`, `/custom-token/`, `/logout/`, `/validate/` |
| [`services/svc-auth/auth_service/views/auth.py`](file:///Users/susurito/Desktop/2026/Buap/Arquitectura%20de%20software/biblioteca_backend/services/svc-auth/auth_service/views/auth.py) | Lógica de auth adaptada + nuevo endpoint `ValidateToken` |
| [`nginx/nginx.conf`](file:///Users/susurito/Desktop/2026/Buap/Arquitectura%20de%20software/biblioteca_backend/nginx/nginx.conf) | API Gateway: rutas auth → svc-auth, resto → monolito |

### 📝 Archivos Modificados

| Archivo | Cambio |
| :--- | :--- |
| [`docker-compose.yml`](file:///Users/susurito/Desktop/2026/Buap/Arquitectura%20de%20software/biblioteca_backend/docker-compose.yml) | +3 servicios: `nginx`, `svc-auth`, `db-auth`. Puerto de `web` pasó de expuesto a `expose` interno |

---

### 🛠️ Detalle de Cambios Clave

#### 1. `svc-auth` — Servicio de autenticación independiente
- **Sin modelos de dominio propios:** Ya no define `Alumnos` ni `Administradores` directamente. Consulta a `svc-usuarios` via HTTP con fallback graceful (si svc-usuarios no está disponible, continúa con `auth.User` local).
- **Misma `SECRET_KEY`:** Crítico para compatibilidad durante la migración Strangler Fig. Los tokens emitidos por el monolito son válidos en svc-auth y viceversa.
- **Django mínimo:** Sin `django.contrib.admin`, sin templates, sin sesiones. Solo lo necesario para auth: `auth`, `rest_framework`, `rest_framework.authtoken`.

#### 2. Endpoint nuevo: `GET /validate/`
```
GET /validate/
Authorization: Token <token>

→ 200 { valid: true, user_id, username, email, nombre, rol, grupos }
→ 401 { detail: "Authentication credentials were not provided." }
```
Permite que `svc-libros` y `svc-prestamos` (Fases 3 y 4) validen tokens sin implementar auth propia.

#### 3. Nginx como API Gateway (patrón Strangler Fig)
```nginx
# Rutas de auth → svc-auth
location ~ ^/(token|custom-token|logout|validate)/ {
    proxy_pass http://svc_auth;
}

# Todo lo demás → monolito (sin cambios)
location / {
    proxy_pass http://monolito;
}
```
El frontend **solo cambia el puerto de 8000 a 8080**. Las rutas son idénticas.

#### 4. BD separada para svc-auth (`db-auth`)
- Contiene únicamente: `auth_user`, `authtoken_token`, `auth_group`, `auth_user_groups`
- Puerto: `3308` del host (para no colisionar con la BD del monolito en `3307`)
- Las credenciales de usuarios existentes deben migrarse con un script (ver siguiente sección)

---

### 🔄 Script de Migración de Usuarios (ejecutar UNA sola vez)

Para sincronizar los usuarios del monolito a la nueva BD de `svc-auth`:

```bash
# 1. Exportar usuarios del monolito
docker compose exec web python manage.py dumpdata \
  auth.User auth.Group auth.Permission \
  authtoken.Token \
  --natural-foreign --natural-primary \
  -o /app/users_export.json

# 2. Copiar el archivo al contexto de svc-auth
docker compose cp web:/app/users_export.json ./services/svc-auth/users_export.json

# 3. Importar en la BD de svc-auth
docker compose exec svc-auth python manage.py loaddata /app/users_export.json
```

---

### ✅ Comandos Docker para levantar la Fase 1

```bash
# Levantar todo (monolito + svc-auth + nginx + ambas BDs)
docker compose up --build -d

# Ver logs de svc-auth
docker compose logs -f svc-auth

# Ver logs del API Gateway
docker compose logs -f nginx

# Verificar que svc-auth responde (a través del gateway)
curl -X POST http://localhost:8080/token/ \
  -H "Content-Type: application/json" \
  -d '{"username": "tu_usuario", "password": "tu_password"}'

# Verificar que el monolito sigue respondiendo por el gateway
curl http://localhost:8080/libros/
```

---

### ⚠️ Consideraciones Importantes

> **Cambio de puerto para el frontend:** El frontend debe actualizar su `baseURL` de `http://localhost:8000` a `http://localhost:8080`. Las rutas son idénticas, solo cambia el puerto.

> **Sincronización de usuarios:** La primera vez que se levante svc-auth, su BD `auth_db` estará vacía. Ejecutar el script de migración de usuarios antes de hacer pruebas de login.

> **El monolito sigue siendo la fuente de verdad:** Hasta la Fase 5, los usuarios se crean y modifican en el monolito. La sincronización hacia svc-auth es manual en esta fase.

---

## 🔵 Fase 2: Extracción de `svc-usuarios` (Próxima)

*(Esta sección se completará al ejecutar la Fase 2)*

- [ ] Crear `services/svc-usuarios/` con Django mínimo
- [ ] Migrar `views/users.py` y `views/alumnos.py` al nuevo servicio
- [ ] Migrar modelos `Alumnos` y `Administradores` con sus migraciones
- [ ] Implementar endpoint interno `GET /internal/resolver-usuario/?q=<query>` para svc-auth
- [ ] Actualizar nginx para enrutar `/alumnos/`, `/register/`, `/perfil/` → svc-usuarios
- [ ] Sincronizar datos de alumnos/admins del monolito a db-usuarios

---

## 📌 Pendientes Post-Migración (después de Fase 5)

### Frontend — Ajustes al terminar todas las fases

- [ ] **Cambiar `baseURL`** de `:8000` → `:8080` (API Gateway)
- [ ] **Revisar respuesta del login:** `svc-auth` devuelve `{ token, user_id, username, email, nombre, rol }` en vez del objeto de alumno/admin completo que devolvía el monolito. Ajustar el componente de login si es necesario.
