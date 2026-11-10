FROM python:3.11-slim
WORKDIR /app
RUN apt-get update && apt-get install -y --no-install-recommends default-libmysqlclient-dev gcc pkg-config && rm -rf /var/lib/apt/lists/*
COPY services/svc-identidad/requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt
COPY services/common /common
ENV PYTHONPATH=/common
COPY services/svc-identidad/ .
EXPOSE 8001
CMD ["gunicorn", "identidad_service.wsgi:application", "--bind", "0.0.0.0:8001", "--access-logfile", "-"]
