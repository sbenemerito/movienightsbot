FROM python:3.11-slim

# tzdata so TZ is honoured -- the poll schedule depends on the local weekday
RUN apt-get update \
    && apt-get install -y --no-install-recommends tzdata \
    && rm -rf /var/lib/apt/lists/*

ENV PYTHONUNBUFFERED=1 \
    DB_PATH=/data/data.sqlite

WORKDIR /app
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt
COPY . .

VOLUME /data
CMD ["python", "main.py"]
