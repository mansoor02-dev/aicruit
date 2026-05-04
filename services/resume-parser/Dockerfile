FROM python:3.11-slim

WORKDIR /app

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1

# Runtime system deps for pymupdf, python-docx, pytesseract image OCR, libmagic
RUN apt-get update && apt-get install -y --no-install-recommends \
    libmagic1 \
    tesseract-ocr \
    && rm -rf /var/lib/apt/lists/*

COPY requirements.txt .
RUN pip install --no-cache-dir --upgrade pip && \
    pip install --no-cache-dir -r requirements.txt

COPY app/ ./app/

ENV GEMINI_API_KEY=""

EXPOSE 8006

CMD ["sh", "-c", "gunicorn app.api:app -k uvicorn.workers.UvicornWorker -w 2 -b 0.0.0.0:${PORT:-8006}"]
