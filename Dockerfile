FROM python:3.9-slim

WORKDIR /app

# Installation des dépendances système
RUN apt-get update && \
    apt-get install -y --no-install-recommends gcc python3-dev libssl-dev curl && \
    apt-get clean && \
    rm -rf /var/lib/apt/lists/*

# Copie des fichiers nécessaires
COPY requirements.txt .
COPY bot_cloud.py .
COPY start.py .
COPY xapi ./xapi

# Installation des dépendances Python
RUN pip install --no-cache-dir -r requirements.txt

# Configuration des variables d'environnement
ENV PORT=8080
ENV XTB_USER_ID="17373384"
ENV XTB_PASSWORD="Java090214&Clement06032005*"

# Exposition explicite du port
EXPOSE 8080

# Healthcheck avec un délai plus long
HEALTHCHECK --interval=60s --timeout=60s --start-period=120s --retries=5 \
    CMD curl -f http://localhost:$PORT/health || exit 1

# Démarrage de l'application
CMD ["python", "start.py"]
