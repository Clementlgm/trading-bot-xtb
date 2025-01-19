FROM python:3.9-slim

WORKDIR /app

# Installation des dépendances système
RUN apt-get update && \
    apt-get install -y --no-install-recommends gcc python3-dev libssl-dev && \
    rm -rf /var/lib/apt/lists/*

# Copie des fichiers nécessaires
COPY requirements.txt .
COPY bot_cloud.py .
COPY xapi/ ./xapi/

# Installation des dépendances Python
RUN pip install --no-cache-dir -r requirements.txt
RUN pip install flask gunicorn

# Configuration des variables d'environnement
ENV XTB_USER_ID=${XTB_USER_ID}
ENV XTB_PASSWORD=${XTB_PASSWORD}
ENV PORT=8080

# Copie du script de démarrage
COPY start.py .

# Démarrage avec Gunicorn
CMD exec gunicorn --bind :$PORT start:app