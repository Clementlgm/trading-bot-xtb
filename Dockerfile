FROM python:3.9-slim

WORKDIR /app

# Installation des dépendances système
RUN apt-get update && \
    apt-get install -y --no-install-recommends gcc python3-dev libssl-dev && \
    apt-get clean && \
    rm -rf /var/lib/apt/lists/*

# Copie des fichiers nécessaires
COPY requirements.txt .
COPY bot_cloud.py .
COPY start.py .
COPY xapi/ ./xapi/
COPY config.yaml .

# Fix des permissions
RUN chmod 755 /app/*.py && \
    chmod 755 /app/xapi/*.py && \
    chmod 644 /app/config.yaml && \
    chmod 644 /app/requirements.txt

# Installation des dépendances Python
RUN pip install --no-cache-dir -r requirements.txt

# Variables d'environnement
ENV PORT=8080

# Démarrage de l'application
CMD ["python", "start.py"]
