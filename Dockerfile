FROM python:3.9-slim

WORKDIR /app

# Installation des dépendances système
RUN apt-get update && \
    apt-get install -y --no-install-recommends gcc python3-dev libssl-dev && \
    apt-get clean && \
    rm -rf /var/lib/apt/lists/*

# Copie des fichiers
COPY requirements.txt .
COPY bot_cloud.py .
COPY start.py .
COPY xapi ./xapi

# Installation des dépendances Python
RUN pip install --no-cache-dir -r requirements.txt

# Configuration des variables d'environnement
ENV PORT=8080

# Démarrage
CMD ["python", "start.py"]
