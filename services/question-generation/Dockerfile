# ===============================
# Builder stage
# ===============================
FROM python:3.12-slim AS builder

ENV DEBIAN_FRONTEND=noninteractive \
    PIP_NO_CACHE_DIR=1 \
    PYTHONDONTWRITEBYTECODE=1

# Install build dependencies needed to build wheels
RUN apt-get update && \
    apt-get install -y --no-install-recommends \
        build-essential \
        gcc \
        g++ \
        git \
        libgomp1 \
    && rm -rf /var/lib/apt/lists/*

WORKDIR /app

# Copy requirements first for better caching
COPY requirements.txt ./

# Build wheels for all requirements to speed up installation in runtime image
RUN pip install --upgrade pip setuptools wheel && \
    pip wheel --wheel-dir /wheels -r requirements.txt


FROM python:3.12-slim

ENV PYTHONUNBUFFERED=1 \
    PYTHONDONTWRITEBYTECODE=1 \
    PIP_NO_CACHE_DIR=1

# Runtime-only system deps
RUN apt-get update && \
    apt-get install -y --no-install-recommends \
        libgomp1 \
    && rm -rf /var/lib/apt/lists/*

# Create non-root user
RUN useradd -m appuser || true

WORKDIR /app

# Copy wheels from builder and install
COPY --from=builder /wheels /wheels
COPY requirements.txt ./
RUN pip install --upgrade pip && \
    pip install --no-index --find-links /wheels -r requirements.txt

# Copy application code
COPY . .

# Create logs directory and set permissions
RUN mkdir -p logs && chown -R appuser:appuser /app

USER appuser

EXPOSE 8010

# Start the FastAPI app
CMD ["uvicorn", "app.api:app", "--host", "0.0.0.0", "--port", "8010", "--proxy-headers"]
