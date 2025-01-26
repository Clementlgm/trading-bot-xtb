FROM python:3.9-slim

WORKDIR /app

# Install build dependencies
RUN apt-get update && \
    apt-get install -y --no-install-recommends gcc python3-dev libssl-dev && \
    apt-get clean && \
    rm -rf /var/lib/apt/lists/*

# Copy all application files
COPY . .

# Install dependencies
RUN pip install --no-cache-dir -r requirements.txt

ENV PYTHONUNBUFFERED=1
ENV PORT=8080

CMD exec gunicorn --bind :$PORT --workers 1 --threads 8 --timeout 0 start:app
