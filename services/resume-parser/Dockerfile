# ── Stage 1: Builder ──────────────────────────────────────────────
FROM python:3.11-slim AS builder

WORKDIR /build

RUN apt-get update && apt-get install -y --no-install-recommends \
    gcc g++ cmake make \
    && rm -rf /var/lib/apt/lists/*

COPY requirements.txt .
RUN pip install --upgrade pip && \
    pip install --prefix=/install --no-cache-dir -r requirements.txt


# ── Stage 2: Runtime ──────────────────────────────────────────────
FROM python:3.11-slim AS runtime

WORKDIR /app

RUN apt-get update && apt-get install -y --no-install-recommends \
    tesseract-ocr \
    libglib2.0-0 libgl1 \
    && rm -rf /var/lib/apt/lists/*

COPY --from=builder /install /usr/local

COPY app/ .

ENV GEMINI_API_KEY=""
ENV MODEL_PATH="/app/models/qwen2.5-1.5b-instruct-q4_k_m.gguf"
ENV INFERENCE_BACKEND="gemini"

EXPOSE 8006

CMD ["uvicorn", "api:app", "--host", "0.0.0.0", "--port", "8006"]