FROM python:3.13-slim

# Chromium: lo usa la vista de exportación a PDF (headless, vía subprocess).
RUN apt-get update && apt-get install -y --no-install-recommends \
    chromium \
    && rm -rf /var/lib/apt/lists/*

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1

WORKDIR /app

COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

COPY . .

RUN chmod +x scripts/docker-entrypoint.sh

EXPOSE 8000
ENTRYPOINT ["scripts/docker-entrypoint.sh"]
