# ── CPU-only TTS System Dockerfile ───────────────────────────────
# Multi-stage build for minimal final image

# ── Stage 1: builder ─────────────────────────────────────────────
FROM python:3.11-slim AS builder

WORKDIR /build

# OS deps for audio processing
RUN apt-get update && apt-get install -y --no-install-recommends \
    ffmpeg \
    espeak-ng \
    libespeak-ng1 \
    && rm -rf /var/lib/apt/lists/*

COPY requirements.txt .
RUN pip install --no-cache-dir --prefix=/install \
    gtts pydub pyttsx3 fastapi "uvicorn[standard]" python-dotenv

# Optional: pre-download a Piper voice model
# RUN pip install --no-cache-dir --prefix=/install piper-tts && \
#     python -c "from piper import PiperVoice; PiperVoice.load('en_US-lessac-medium')"

# ── Stage 2: runtime ──────────────────────────────────────────────
FROM python:3.11-slim AS runtime

WORKDIR /app

RUN apt-get update && apt-get install -y --no-install-recommends \
    ffmpeg \
    espeak-ng \
    libespeak-ng1 \
    && rm -rf /var/lib/apt/lists/*

COPY --from=builder /install /usr/local
COPY . .

# Environment
ENV PYTHONUNBUFFERED=1 \
    PYTHONPATH=/app \
    TTS_DEFAULT_PROVIDER=auto \
    LOG_LEVEL=INFO

EXPOSE 8011

# Health-check via REST endpoint
HEALTHCHECK --interval=30s --timeout=5s --start-period=10s --retries=3 \
    CMD python -c "import urllib.request; urllib.request.urlopen('http://localhost:8000/health')"

# Default: run REST API
CMD ["uvicorn", "interface.api:app", "--host", "0.0.0.0", "--port", "8011"]

# Override for CLI:
#   docker run tts python main.py --text "Hello" --provider local