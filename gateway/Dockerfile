FROM python:3.12-slim

WORKDIR /app

COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

COPY . .

ENV PORT=8000

# Use package path for uvicorn so it finds the `app` package
CMD uvicorn app.main:app --host 0.0.0.0 --port $PORT