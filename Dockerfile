FROM python:3.9-slim

WORKDIR /app

RUN apt-get update && \
    apt-get install -y --no-install-recommends gcc python3-dev libssl-dev && \
    apt-get clean && \
    rm -rf /var/lib/apt/lists/*

COPY . .
RUN pip install --no-cache-dir -r requirements.txt

ENV PORT=8080
ENV PYTHONUNBUFFERED=1
ENV GUNICORN_TIMEOUT=300

CMD exec gunicorn --bind 0.0.0.0:$PORT --workers 1 --threads 8 --timeout $GUNICORN_TIMEOUT start:app
