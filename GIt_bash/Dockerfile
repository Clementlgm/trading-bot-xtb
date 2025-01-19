FROM python:3.9-slim

WORKDIR /app

# Installation des dépendances système
RUN apt-get update && \
    apt-get install -y --no-install-recommends gcc python3-dev libssl-dev && \
    rm -rf /var/lib/apt/lists/*

# Copie des fichiers nécessaires
COPY requirements.txt .
COPY bot_cloud.py .
COPY /xapi/ ./xapi/

# Installation des dépendances Python
RUN pip install --no-cache-dir -r requirements.txt

# Configuration des variables d'environnement
ENV UTILISATEUR_XTB=${UTILISATEUR_XTB}
ENV XTB_MOT_DE_PASSE=${XTB_MOT_DE_PASSE}
ENV PORT=8080

CMD ["python", "bot_cloud.py"]
