FROM python:3.9-slim

WORKDIR /app

# Installation des dépendances système avec nettoyage dans la même couche
RUN apt-get update && \
    apt-get install -y --no-install-recommends gcc python3-dev libssl-dev && \
    apt-get clean && \
    rm -rf /var/lib/apt/lists/* && \
    rm -rf /var/lib/apt/lists/*

# Copie des fichiers nécessaires
COPY requirements.txt .
COPY bot_cloud.py .
COPY start.py .
COPY xapi ./xapi

# Installation des dépendances Python avec mise en cache désactivée
RUN pip install --no-cache-dir -r requirements.txt && \
    rm -rf /root/.cache/pip/*

# Configuration des variables d'environnement
ENV PORT=8080
ENV XTB_USER_ID="17373384"
ENV XTB_PASSWORD="Java090214&Clement06032005*"

# Configuration du healthcheck
HEALTHCHECK --interval=30s --timeout=30s --start-period=5s --retries=3 \
    CMD curl -f http://localhost:8080/health || exit 1

# Démarrage de l'application
CMD ["python", "start.py"]
