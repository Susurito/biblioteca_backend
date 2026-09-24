# ====================================
# Dockerfile - biblioteca_backend
# ====================================

# Imagen base oficial de Python (slim = ligera, sin extras innecesarios)
FROM python:3.10-slim

# Variables de entorno: evita archivos .pyc y habilita logs en tiempo real
ENV PYTHONDONTWRITEBYTECODE=1
ENV PYTHONUNBUFFERED=1

# Instalar dependencias del sistema necesarias para compilar mysqlclient
RUN apt-get update \
    && apt-get install -y \
        default-libmysqlclient-dev \
        build-essential \
        pkg-config \
    && rm -rf /var/lib/apt/lists/*

# Establecer el directorio de trabajo dentro del contenedor
WORKDIR /app

# Copiar primero solo el requirements para aprovechar caché de capas de Docker
COPY requirements.txt /app/

# Instalar dependencias de Python
RUN pip install --upgrade pip && pip install -r requirements.txt

# Copiar el resto del proyecto
COPY . /app/

# Exponer el puerto donde correrá Django
EXPOSE 8000

# Comando de arranque
CMD ["python", "manage.py", "runserver", "0.0.0.0:8000"]
