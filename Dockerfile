FROM python:3.9-slim

WORKDIR /app

# Copie des fichiers
COPY . .

# Installation des dépendances
RUN pip install --no-cache-dir -r requirements.txt

# Variables d'environnement
ENV PORT=8080

# Démarrage
CMD ["python", "start.py"]
