# ── Stage 1: Builder (with build tools for compilation) ──────
FROM python:3.11-slim AS builder

WORKDIR /build

# Install build-time dependencies (needed for compiling native extensions)
RUN apt-get update && apt-get install -y --no-install-recommends \
    gcc g++ cmake make \
    && rm -rf /var/lib/apt/lists/*

# Copy requirements and compile to /install prefix (wheels for runtime)
COPY requirements.txt .
RUN pip install --upgrade pip && \
    pip install --prefix=/install --no-cache-dir -r requirements.txt


# ── Stage 2: Runtime (minimal, no build tools) ────────────────
FROM python:3.11-slim

WORKDIR /app

# Prevent Python from writing .pyc files and buffer I/O
ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1

# Install runtime-only dependencies (OCR support, image libraries)
RUN apt-get update && apt-get install -y --no-install-recommends \
    tesseract-ocr \
    libglib2.0-0 libgl1 \
    && rm -rf /var/lib/apt/lists/*

# Copy pre-built wheels and packages from builder stage
COPY --from=builder /install /usr/local

# Copy application code
COPY app/ .

# Configuration variables
ENV GEMINI_API_KEY="" \
    MODEL_PATH="/app/models/qwen2.5-1.5b-instruct-q4_k_m.gguf" \
    INFERENCE_BACKEND="gemini"

EXPOSE 8006

# Run application (explicit format = better signal handling)
CMD ["uvicorn", "api:app", "--host", "0.0.0.0", "--port", "8006"]