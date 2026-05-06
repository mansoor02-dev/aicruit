FROM python:3.11-slim

WORKDIR /app

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1

COPY requirements.txt .
RUN pip install --upgrade pip && \
    pip install --no-cache-dir -r requirements.txt

COPY . .

EXPOSE 8010

CMD ["sh", "-c", "gunicorn -k uvicorn.workers.UvicornWorker -w 2 --timeout 300 -b 0.0.0.0:${PORT:-8010} app.main:app"]
