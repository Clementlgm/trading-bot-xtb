FROM python:3.9-slim

WORKDIR /app

RUN apt-get update && \
    apt-get install -y gcc python3-dev libssl-dev && \
    apt-get clean && \
    rm -rf /var/lib/apt/lists/*

COPY requirements.txt .
RUN pip install --no-cache-dir gunicorn flask python-dotenv

COPY . .

ENV PYTHONUNBUFFERED=1
ENV PORT=8080
ENV XTB_USER_ID="17373384"
ENV XTB_PASSWORD="Java090214&Clement06032005*"

EXPOSE 8080

CMD gunicorn start:app --bind 0.0.0.0:$PORT --workers 1 --threads 8 --timeout 0