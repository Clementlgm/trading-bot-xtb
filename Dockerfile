FROM python:3.9-slim

WORKDIR /app

RUN apt-get update && \
    apt-get install -y --no-install-recommends gcc python3-dev libssl-dev && \
    apt-get clean && \
    rm -rf /var/lib/apt/lists/*

COPY requirements.txt .
COPY *.py .
COPY xapi/ ./xapi/

RUN pip install --no-cache-dir -r requirements.txt

ENV PORT=8080

CMD ["python", "start.py"]
