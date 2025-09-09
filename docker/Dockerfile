# syntax=docker/dockerfile:1
FROM python:3.13-slim

# Environment
# Stop creating .pyc files → cleaner container.
# Flush logs immediately → better visibility in Cloud Run.
ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1

# Install system dependencies
RUN apt-get update && apt-get install -y --no-install-recommends \
    build-essential curl \
    && rm -rf /var/lib/apt/lists/*

WORKDIR /app

# Install Python dependencies
COPY requirements.txt .
RUN pip install --upgrade pip && pip install -r requirements.txt

# Copy app source
COPY src/ ./src/

# Expose port Cloud Run expects
EXPOSE 8080

# Run FastAPI via Uvicorn (single process)
CMD ["uvicorn", "src.main:app", "--host", "0.0.0.0", "--port", "8080"]