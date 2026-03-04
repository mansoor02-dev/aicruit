# ── CPU-only TTS System Dockerfile (Piper TTS) ──────────────────
FROM python:3.11-slim

WORKDIR /app

# OS deps for audio processing
RUN apt-get update && apt-get install -y --no-install-recommends \
    espeak-ng \
    libespeak-ng1 \
    && rm -rf /var/lib/apt/lists/*

COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

COPY . .

ENV PYTHONUNBUFFERED=1 \
    PYTHONPATH=/app

ENV PORT=8011

HEALTHCHECK --interval=30s --timeout=5s --start-period=10s --retries=3 \
    CMD python -c "import urllib.request, os; urllib.request.urlopen(f'http://localhost:{os.environ.get(\"PORT\", 8011)}/health')"

# Default: run REST API
CMD uvicorn main:app --host 0.0.0.0 --port $PORT