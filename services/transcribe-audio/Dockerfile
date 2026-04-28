# ── Python 3.11 slim image with audio/transcription support ──
FROM python:3.11-slim

WORKDIR /app

# Prevent Python from writing .pyc files and buffer I/O
ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1

# Install audio/transcription system dependencies
# ffmpeg = audio/video processing, needed for audio format conversion
RUN apt-get update && apt-get install -y --no-install-recommends \
    ffmpeg \
    && rm -rf /var/lib/apt/lists/*

# Copy only requirements first (enables layer caching)
COPY requirements.txt .

# Install Python dependencies (--no-cache-dir = don't cache wheels locally)
RUN pip install --no-cache-dir -r requirements.txt

# Copy application code after dependencies
COPY . .

EXPOSE 8007

# Run application (explicit format = better signal handling)
CMD ["uvicorn", "app.main:app", "--host", "0.0.0.0", "--port", "8007"]
