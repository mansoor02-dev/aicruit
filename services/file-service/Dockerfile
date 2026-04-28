# ── Python 3.11 slim image (small base, includes essentials)
FROM python:3.11-slim

# Set working directory
WORKDIR /app

# Prevent Python from writing .pyc files (reduces size and I/O)
ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1

# Copy only requirements first (enables layer caching: if requirements unchanged, skip reinstall)
COPY requirements.txt .

# Install Python dependencies (--no-cache-dir = don't cache wheels locally, saves space)
RUN pip install --no-cache-dir -r requirements.txt

# Copy application code after dependencies (code changes won't bust requirements layer)
COPY . .

# Expose port
EXPOSE 8005

# Run application (explicit list format = better signal handling)
CMD ["uvicorn", "app.main:app", "--host", "0.0.0.0", "--port", "8005"]