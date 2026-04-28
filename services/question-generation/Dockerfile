# ── Stage 1: Builder (with build tools) ──────────────────────
FROM python:3.11-slim AS builder

WORKDIR /build

# Install build dependencies (only needed for compilation)
RUN apt-get update && apt-get install -y --no-install-recommends \
    build-essential \
    && rm -rf /var/lib/apt/lists/*

# Copy requirements and build wheels to /install prefix
COPY requirements.txt .
RUN pip install --upgrade pip && \
    pip install --prefix=/install --no-cache-dir --index-url https://download.pytorch.org/whl/cpu torch && \
    pip install --prefix=/install --no-cache-dir -r requirements.txt

# ── Stage 2: Runtime (minimal, no build tools) ────────────────
FROM python:3.11-slim

WORKDIR /app

# Prevent Python from writing .pyc files and buffer I/O (improves startup/shutdown)
ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1

# Copy pre-built wheels and packages from builder stage
COPY --from=builder /install /usr/local

# Copy application code
COPY . .

EXPOSE 8010

# Run application (explicit format = better signal handling)
CMD ["uvicorn", "main:app", "--host", "0.0.0.0", "--port", "8010", "--app-dir", "app"]