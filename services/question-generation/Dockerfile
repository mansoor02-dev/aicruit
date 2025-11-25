# Dockerfile
FROM python:3.12-slim

# Prevent interactive prompts + optimize Python
ENV DEBIAN_FRONTEND=noninteractive \
    PYTHONUNBUFFERED=1 \
    PYTHONDONTWRITEBYTECODE=1 \
    PIP_NO_CACHE_DIR=1

# Install build dependencies
RUN apt-get update && \
    apt-get install -y --no-install-recommends \
        build-essential \
        gcc \
        g++ \
        cmake \
        git \
        curl \
        pkg-config \
        libopenblas-dev \
        libomp-dev \
        && rm -rf /var/lib/apt/lists/*

# Create app directory
WORKDIR /app

# Copy requirements
COPY requirements.txt .

# Install Python packages with special handling for llama-cpp-python
RUN pip install --upgrade pip && \
    \
    # First install everything EXCEPT llama-cpp-python
    grep -v "llama-cpp-python" requirements.txt | xargs pip install --no-cache-dir && \
    \
    # Now install llama-cpp-python with modern CPU support
    CMAKE_ARGS="-DLLAMA_BLAS=ON -DLLAMA_BLAS_VENDOR=OpenBLAS -DLLAMA_AVX2=ON -DLLAMA_FMA=ON -DLLAMA_F16C=ON" \
    FORCE_CMAKE=1 \
    pip install --no-cache-dir --force-reinstall --no-binary=llama-cpp-python llama-cpp-python

# Copy project
COPY . .

# Create required directories
RUN mkdir -p cache logs models/llm

# Download model if not exists (optional but recommended)
# RUN if [ ! -f models/llm/Phi-3-mini-4k-instruct-q4.gguf ]; then \
#     curl -L -o models/llm/Phi-3-mini-4k-instruct-q4.gguf \
#     https://huggingface.co/microsoft/Phi-3-mini-4k-instruct-gguf/resolve/main/Phi-3-mini-4k-instruct-q4.gguf; \
#     fi

EXPOSE 8000

# Run the API (not main.py — you want the FastAPI server)
CMD ["uvicorn", "app.api:app", "--host", "0.0.0.0", "--port", "8000"]