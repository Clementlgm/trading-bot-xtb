FROM python:3.9-slim

WORKDIR /app

# Installation des dépendances
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# Copie des fichiers
COPY . .

# Variables d'environnement
ENV PORT=8080

# Commande de démarrage avec gunicorn
CMD exec gunicorn --bind :$PORT --workers 1 --threads 8 --timeout 0 start:app
