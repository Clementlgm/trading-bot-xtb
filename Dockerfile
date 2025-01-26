FROM python:3.9-slim

WORKDIR /app

RUN apt-get update && \
    apt-get install -y --no-install-recommends gcc python3-dev libssl-dev && \
    apt-get clean && \
    rm -rf /var/lib/apt/lists/*

# Copier d'abord les fichiers de configuration
COPY requirements.txt .
COPY Dockerfile .
COPY cloudbuild.yaml .

# Copier les fichiers Python
COPY bot_cloud.py .
COPY start.py .
COPY __init__.py .

# Copier le dossier xapi complet
COPY xapi/ ./xapi/

RUN pip install --no-cache-dir -r requirements.txt

ENV PORT=8080
ENV PYTHONUNBUFFERED=1

CMD exec gunicorn --bind :$PORT --workers 1 --threads 8 --timeout 0 "start:app"
