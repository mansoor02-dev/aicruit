FROM python:3.11-slim

WORKDIR /app

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1

# Runtime system dependency for pytesseract image OCR.
RUN apt-get update && apt-get install -y --no-install-recommends \
    tesseract-ocr \
    && rm -rf /var/lib/apt/lists/*

COPY requirements.txt .
RUN pip install --no-cache-dir --upgrade pip && \
    pip install --no-cache-dir -r requirements.txt

COPY app/ ./app/

ENV GEMINI_API_KEY=""

EXPOSE 8006

CMD ["sh", "-c", "gunicorn app.api:app -k uvicorn.workers.UvicornWorker -w 2 --timeout 300 -b 0.0.0.0:${PORT:-8006}"]
