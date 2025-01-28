FROM python:3.9-slim

WORKDIR /app

RUN apt-get update && \
    apt-get install -y gcc python3-dev libssl-dev && \
    apt-get clean

COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

COPY . .

ENV PORT=8080
ENV PYTHONUNBUFFERED=1

CMD exec gunicorn --bind :$PORT --workers 1 --threads 8 --timeout 0 start:app