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

# Install Python packages with special handling for llama-cpp-python
# Set hardware acceleration flags for CPU
ENV CMAKE_ARGS="-DLLAMA_BLAS=ON -DLLAMA_BLAS_VENDOR=OpenBLAS -DLLAMA_AVX2=ON -DLLAMA_FMA=ON -DLLAMA_F16C=ON"
ENV FORCE_CMAKE=1

# Install requirements, forcing source build for llama-cpp-python to apply optimizations
RUN pip install --upgrade pip && \
    pip install --no-cache-dir -r requirements.txt --no-binary=llama-cpp-python

# Copy application code
COPY . .

# Create logs directory and set permissions
RUN mkdir -p logs && chown -R appuser:appuser /app

EXPOSE 8000

# Run the API
CMD ["uvicorn", "app.api:app", "--host", "0.0.0.0", "--port", "8000"]
