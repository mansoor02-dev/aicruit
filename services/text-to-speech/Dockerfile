# ── Python 3.11 slim image with audio/TTS support ──────────
FROM python:3.11-slim

WORKDIR /app

# Prevent Python from writing .pyc files and buffer I/O (improves startup)
ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    PYTHONPATH=/app

# Install audio/TTS system dependencies (espeak-ng = text-to-speech engine)
RUN apt-get update && apt-get install -y --no-install-recommends \
    espeak-ng \
    libespeak-ng1 \
    && rm -rf /var/lib/apt/lists/*

# Copy only requirements first (enables layer caching)
COPY requirements.txt .

# Install Python dependencies (--no-cache-dir = don't cache wheels locally)
RUN pip install --no-cache-dir -r requirements.txt

# Copy application code after dependencies
COPY . .

EXPOSE 8011

# Health check: monitor if service is responsive (curl alternative)
HEALTHCHECK --interval=30s --timeout=5s --start-period=10s --retries=3 \
    CMD python -c "import urllib.request, os; urllib.request.urlopen(f'http://localhost:{os.environ.get(\"PORT\", 8011)}/health')"

# Run application (explicit format = better signal handling)
CMD ["uvicorn", "main:app", "--host", "0.0.0.0", "--port", "8011"]