# syntax=docker/dockerfile:1

# Build locally, from the repository root dir:
# docker build -t api:latest -f api/Dockerfile .

FROM python:3.13-slim

# Environment
# Stop creating .pyc files → cleaner container.
# Flush logs immediately → better visibility in logs.
# Don't cache pip downloads → smaller image.
# Disable pip version check → cleaner logs.
# Set Python module search path → predictable imports.
ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    PIP_NO_CACHE_DIR=1 \
    PIP_DISABLE_PIP_VERSION_CHECK=1 \
    PYTHONPATH=/app

# Install system dependencies
RUN apt-get update && apt-get install -y --no-install-recommends \
    build-essential curl \
    && rm -rf /var/lib/apt/lists/*

RUN pip install --upgrade pip 

WORKDIR /app

# Copy shared and api source code
COPY ./api/ ./api/
COPY ./shared/ ./shared/

# Install Python dependencies
RUN pip install -r shared/requirements.txt
RUN pip install -r api/requirements.txt

# Expose port Cloud Run expects
# Expose port 8080 for documentation purposes. Cloud Run ignores EXPOSE, but it's good practice.
EXPOSE 8080

# Useful docs about deploying FastAPI:
# https://fastapi.tiangolo.com/deployment/docker/#dockerfile
# https://fastapi.tiangolo.com/advanced/behind-a-proxy

# IMPORTANT: Cloud Run sets the PORT environment variable dynamically.
# Uvicorn should use this variable to ensure compatibility.
# The following CMD uses the PORT environment variable, which is set by Cloud Run.
# If running locally, PORT defaults to 8080.

# We must use the shell syntax despite advice from the documentation, because we need to expand the PORT variable.
CMD uvicorn api.main:app --host 0.0.0.0 --port ${PORT} --proxy-headers --forwarded-allow-ips="*"
