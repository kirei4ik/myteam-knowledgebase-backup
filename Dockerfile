FROM python:3.12-slim

WORKDIR /app

RUN apt-get update \
    && apt-get install -y --no-install-recommends git \
    && rm -rf /var/lib/apt/lists/*

COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

COPY backup.py .
COPY app/ app/

ENV PYTHONUNBUFFERED=1

# Ключ-точка для persistent volume бэкапов (STORAGE_BACKEND=local).
VOLUME ["/data/backups"]

CMD ["sh", "-c", "sleep infinity"]