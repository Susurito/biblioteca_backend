# 📚 Biblioteca Backend API

API REST para un sistema de gestión de biblioteca escolar, desarrollada con **Django REST Framework** y desplegada con **Docker**.

---

## 🛠️ Stack Tecnológico

| Capa | Tecnología |
|------|-----------|
| Lenguaje | Python 3.10 |
| Framework | Django 5.0.2 + Django REST Framework 3.14 |
| Base de datos | MySQL 8.0 |
| Autenticación | Token-based (DRF AuthToken + JWT via SimpleJWT) |
| Contenedores | Docker + Docker Compose |
| Almacenamiento | Google Cloud Storage |

---

## 📁 Estructura del Proyecto

```
biblioteca_backend/
├── biblioteca_backend/
│   ├── models.py          # Modelos: Administradores, Alumnos, Libros, Prestamos
│   ├── serializers.py     # Serializadores DRF
│   ├── urls.py            # Rutas de la API
│   ├── settings.py        # Configuración de Django
│   ├── views/             # Vistas organizadas por módulo
│   │   ├── auth.py        # Login / Logout
│   │   ├── users.py       # Registro y perfil de usuario
│   │   ├── alumnos.py     # Gestión de alumnos
│   │   └── views.py       # Libros y préstamos
│   └── file_storage/      # Integración con Google Cloud Storage
├── Dockerfile
├── docker-compose.yml
├── requirements.txt
└── manage.py
```

---

## 🗄️ Modelos de Datos

| Modelo | Descripción |
|--------|-------------|
| `Administradores` | Extiende `User` de Django; tiene matrícula única (9 chars) |
| `Alumnos` | Extiende `User`; guarda nombre, apellidos y matrícula (10 chars) |
| `Libros` | Título, autor, género, detalles y estado de disponibilidad |
| `Prestamos` | Relación Alumno ↔ Libro con estados: `pendiente`, `aceptado`, `rechazado` |

---

## 🔌 Endpoints de la API

| Método | Ruta | Descripción | Auth |
|--------|------|-------------|------|
| `POST` | `/custom-token/` | Login — devuelve token | ❌ |
| `POST` | `/token/` | Login (alias) | ❌ |
| `POST` | `/logout/` | Cerrar sesión | ✅ |
| `POST` | `/register/` | Registro de usuario | ❌ |
| `POST` | `/admin/create/` | Crear administrador | ✅ |
| `GET` | `/perfil/` | Perfil del usuario autenticado | ✅ |
| `GET/POST` | `/alumnos/` | Listar / crear alumno | ✅ |
| `GET` | `/alumnos/all/` | Todos los alumnos | ✅ |
| `GET/POST/PUT/DELETE` | `/libros/` | CRUD de libros | ✅ |
| `GET/POST/PUT/DELETE` | `/prestamos/` | CRUD de préstamos | ✅ |
| `POST` | `/solicitar-prestamo/` | Solicitar un préstamo | ✅ |
| `GET` | `/bootstrap/version` | Versión de la API | ❌ |

---

## 🚀 Ejecución con Docker (Recomendado)

### Prerrequisitos
- [Docker Desktop](https://www.docker.com/products/docker-desktop/) instalado y corriendo.

> 💡 **Nota:** Puedes usar indistintamente `docker-compose` o `docker compose` según la versión de Docker instalada en tu equipo.

### Inicio Rápido

```bash
# 1. Clonar el repositorio y acceder a la carpeta
git clone <url-del-repositorio>
cd biblioteca_backend

# 2. Configurar archivo de variables de entorno
cp .env.example .env

# 3. Levantar los contenedores construyendo las imágenes
docker-compose up --build

# 4. La API estará disponible en:
#    http://localhost:8000
```

> El contenedor de Django espera automáticamente a que MySQL esté saludable (`healthy`) antes de ejecutar las migraciones y arrancar el servidor.

### Puertos Expuestos

| Servicio | Puerto en host | Puerto interno | Notas |
|----------|---------------|----------------|-------|
| Django API | `8000` | `8000` | Servidor web |
| MySQL | `3307` | `3306` | Mapeado al 3307 para evitar conflictos con XAMPP / MySQL local |

---

### 📋 Guía de Comandos Docker

#### 🟢 Activar / Iniciar Contenedores

```bash
# Iniciar en segundo plano (modo detached - libera la terminal)
docker-compose up -d

# Iniciar en primer plano (viendo logs de salida en tiempo real)
docker-compose up

# Iniciar y forzar reconstrucción de imágenes
docker-compose up -d --build

# Reanudar contenedores existentes que habían sido detenidos con stop
docker-compose start
```

#### 🔴 Desactivar / Detener Contenedores

```bash
# Detener temporalmente los contenedores sin eliminarlos (conserva el estado)
docker-compose stop

# Detener y remover los contenedores y las redes
docker-compose down

# Detener, remover contenedores y BORRAR el volumen de datos de MySQL (reinicio desde cero)
docker-compose down -v
```

#### 🔄 Aplicar Cambios

```bash
# 1. Si modificaste requirements.txt o Dockerfile (reconstruir la imagen de la app):
docker-compose up -d --build

# 2. Si modificaste models.py (crear y aplicar nuevas migraciones en Django):
docker-compose exec web python manage.py makemigrations
docker-compose exec web python manage.py migrate

# 3. Si modificaste configuraciones y requieres reiniciar solo el backend:
docker-compose restart web

# 4. Reiniciar todos los servicios:
docker-compose restart
```

#### 🛠️ Monitoreo y Utilidades

```bash
# Ver el estado actual de los contenedores
docker-compose ps

# Ver logs en tiempo real (de todos los servicios)
docker-compose logs -f

# Ver logs en tiempo real únicamente del backend (Django)
docker-compose logs -f web

# Ver logs en tiempo real de MySQL
docker-compose logs -f db

# Entrar a una terminal interactiva (bash) dentro del contenedor de Django
docker-compose exec web bash

# Crear un superusuario administrador de Django en el contenedor
docker-compose exec web python manage.py createsuperuser

# Entrar a la consola de base de datos MySQL dentro del contenedor
docker-compose exec db mysql -u root -prootpassword biblioteca1_db
```

---

## 🖥️ Ejecución Local (sin Docker)

### Prerrequisitos

- Python 3.10+
- MySQL 8.0 corriendo localmente
- `pip`

### Pasos

```bash
# 1. Crear y activar entorno virtual
python -m venv env

# Linux / macOS:
source env/bin/activate

# Windows:
env\Scripts\activate.bat

# 2. Instalar dependencias
pip install -r requirements.txt

# 3. Configurar conexión a MySQL
#    Edita el archivo: my.cnf

# 4. Aplicar migraciones
python manage.py makemigrations
python manage.py migrate

# 5. (Opcional) Crear superusuario administrador
python manage.py createsuperuser --email admin@admin.com --username admin

# 6. Correr el servidor de desarrollo
python manage.py runserver
```

---

## ⚙️ Variables de Entorno

Cuando se usa Docker Compose, las variables se pasan automáticamente al contenedor `web`:

| Variable | Valor por defecto | Descripción |
|----------|------------------|-------------|
| `DB_HOST` | `db` | Host de MySQL (nombre del servicio Docker) |
| `DB_NAME` | `biblioteca1_db` | Nombre de la base de datos |
| `DB_USER` | `root` | Usuario de MySQL |
| `DB_PASSWORD` | `rootpassword` | Contraseña de MySQL |
| `DB_PORT` | `3306` | Puerto interno de MySQL |

---

## 📦 Dependencias Principales

```
Django==5.0.2
djangorestframework==3.14.0
djangorestframework-simplejwt==5.3.1
django-cors-headers==4.3.1
django-filter==23.5
mysqlclient==2.2.7
google-cloud-storage
```

---

## 👤 Autores

Proyecto desarrollado para la materia de **Arquitectura de Software** — BUAP, 8vo Semestre.

---

## 🏗️ Arquitectura de Microservicios

El proyecto actualmente es un **monolito Django**. A continuación se documenta la arquitectura de microservicios usando el patrón **Strangler Fig**.

### Bounded Contexts Identificados

```
                         ┌─────────────────┐
                         │  API GATEWAY    │  :8080
                         │     (nginx)     │
                         └────────┬────────┘
                                  │
              ┌───────────────────┼───────────────────┐
              │                   │                   │           
     ┌────────▼────────┐ ┌────────▼────────┐ ┌───────▼────────┐ ┌────────▼────────┐
     │  1. svc-auth    │ │ 2. svc-usuarios │ │ 3. svc-libros  │ │4. svc-prestamos │
     │     :8001       │ │     :8002       │ │    :8003       │ │     :8004       │
     │                 │ │                 │ │                │ │                 │
     │ • Login/Logout  │ │ • Alumnos CRUD  │ │ • Catálogo     │ │ • Solicitudes   │
     │ • JWT/Token     │ │ • Admins CRUD   │ │ • Disponib.    │ │ • Aprobaciones  │
     │ • Validar token │ │ • Perfil        │ │ • Storage GCS  │ │ • Devoluciones  │
     │                 │ │ • Registro      │ │                │ │ • Multas/Bloqueo│
     └────────┬────────┘ └────────┬────────┘ └───────┬────────┘ └────────┬────────┘
              │                   │                   │                   │
     ┌────────▼────────┐ ┌────────▼────────┐ ┌───────▼────────┐ ┌────────▼────────┐
     │   MySQL:auth    │ │  MySQL:usuarios │ │  MySQL:libros  │ │ MySQL:prestamos │
     └─────────────────┘ └─────────────────┘ └────────────────┘ └─────────────────┘
```

### Estructura de Directorios Objetivo

```
biblioteca_backend/                   ← Repositorio raíz
├── .env
├── .env.example
├── .gitignore
├── docker-compose.yml                ← Orquesta todos los servicios
├── README.md
│
├── nginx/
│   └── nginx.conf                    ← API Gateway / reverse proxy
│
└── services/
    ├── svc-auth/                     ← Microservicio 1: Autenticación
    │   ├── Dockerfile
    │   ├── requirements.txt
    │   ├── manage.py
    │   └── auth_service/
    │       ├── settings.py
    │       ├── urls.py
    │       └── views/
    │           └── auth.py           ← CustomAuthToken, Logout
    │
    ├── svc-usuarios/                 ← Microservicio 2: Usuarios y Alumnos
    │   ├── Dockerfile
    │   ├── requirements.txt
    │   ├── manage.py
    │   └── usuarios_service/
    │       ├── models.py             (Alumnos, Administradores)
    │       ├── serializers.py
    │       ├── urls.py
    │       └── views/
    │           ├── users.py
    │           └── alumnos.py
    │
    ├── svc-libros/                   ← Microservicio 3: Catálogo de Libros
    │   ├── Dockerfile
    │   ├── requirements.txt
    │   ├── manage.py
    │   └── libros_service/
    │       ├── models.py             (Libros)
    │       ├── serializers.py
    │       ├── urls.py
    │       ├── views/
    │       │   └── libros.py         ← LibrosViewSet
    │       └── file_storage/         ← Integración Google Cloud Storage
    │
    └── svc-prestamos/                ← Microservicio 4: Préstamos (el más complejo)
        ├── Dockerfile
        ├── requirements.txt
        ├── manage.py
        └── prestamos_service/
            ├── models.py             (Prestamos — FK reemplazadas por IntegerField)
            ├── serializers.py
            ├── urls.py
            ├── views/
            │   └── prestamos.py      ← PrestamosViewSet, SolicitarPrestamoView
            └── business/
                └── reglas.py         ← verificar_bloqueo_alumno (Regla RN-04)
```

### Tabla de Microservicios

| # | Servicio | Puerto | Extrae de (monolito) | BD propia |
|---|----------|--------|----------------------|-----------|
| 1 | `svc-auth` | 8001 | `views/auth.py` | `auth_db` |
| 2 | `svc-usuarios` | 8002 | `views/users.py` + `views/alumnos.py` | `usuarios_db` |
| 3 | `svc-libros` | 8003 | `LibrosViewSet` + `file_storage/` | `libros_db` |
| 4 | `svc-prestamos` | 8004 | `PrestamosViewSet` + lógica RN-04 | `prestamos_db` |

### Roadmap de Migración (Patrón Strangler Fig)

| Fase | Descripción | Estado |
|------|-------------|--------|
| **Fase 0** | Limpieza del monolito: eliminar código comentado, consolidar serializers duplicados | 🔵 Pendiente |
| **Fase 1** | Extraer `svc-auth` + configurar nginx como API Gateway | 🔵 Pendiente |
| **Fase 2** | Extraer `svc-usuarios` (Alumnos, Administradores, Perfil) | 🔵 Pendiente |
| **Fase 3** | Extraer `svc-libros` (Catálogo + GCS) | 🔵 Pendiente |
| **Fase 4** | Extraer `svc-prestamos` (Préstamos + RN-04 + patrón Saga) | 🔵 Pendiente |
| **Fase 5** | Retirar el monolito original | 🔵 Pendiente |

> **Nota académica:** Para el alcance de la materia, implementar hasta la **Fase 2** (svc-auth + svc-usuarios con nginx) es suficiente para demostrar dominio de la arquitectura de microservicios.