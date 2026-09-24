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

### Pasos

```bash
# 1. Clonar el repositorio
git clone <url-del-repositorio>
cd biblioteca_backend

# 2. Levantar los contenedores (MySQL + Django)
docker-compose up --build

# 3. La API estará disponible en:
#    http://localhost:8000
```

> El contenedor de Django espera automáticamente a que MySQL esté listo antes de ejecutar las migraciones y arrancar el servidor.

### Puertos expuestos

| Servicio | Puerto en host | Puerto interno |
|----------|---------------|----------------|
| Django API | `8000` | `8000` |
| MySQL | `3307` | `3306` |

> ⚠️ El puerto de MySQL está mapeado al **3307** en el host para evitar conflictos con XAMPP.

### Detener los contenedores

```bash
docker-compose down
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