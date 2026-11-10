FROM python:3.11-slim
WORKDIR /app
RUN apt-get update && apt-get install -y --no-install-recommends default-libmysqlclient-dev gcc pkg-config && rm -rf /var/lib/apt/lists/*
COPY services/svc-prestamos/requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt
COPY services/common /common
ENV PYTHONPATH=/common
COPY services/svc-prestamos/ .
EXPOSE 8004
CMD ["gunicorn", "prestamos_service.wsgi:application", "--bind", "0.0.0.0:8004", "--access-logfile", "-"]
