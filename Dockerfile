FROM python:3.12-slim

WORKDIR /app

COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

COPY backup.py .
COPY app/ app/

ENV PYTHONUNBUFFERED=1

CMD ["python", "backup.py"]