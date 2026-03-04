FROM python:3.11-slim

WORKDIR /service

COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

COPY . .

ENV PORT=8012

CMD uvicorn app.main:app --host 0.0.0.0 --port $PORT