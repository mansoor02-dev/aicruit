# syntax=docker/dockerfile:1
FROM python:3.12-slim

RUN apt-get update && \
    apt-get install -y --no-install-recommends \
        tesseract-ocr \
        poppler-utils && \
    rm -rf /var/lib/apt/lists/*

WORKDIR /app

COPY requirements.txt .

# THIS LINE IS THE ONLY CHANGE YOU NEED
RUN pip install --no-cache-dir \
    --index-url https://download.pytorch.org/whl/cpu \
    -r requirements.txt

COPY . .