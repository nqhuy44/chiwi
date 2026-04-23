# Stage 1: Build
FROM python:3.12-slim AS builder

WORKDIR /app
ENV PYTHONDONTWRITEBYTECODE=1
ENV PYTHONUNBUFFERED=1

# Install build dependencies
RUN apt-get update && apt-get install -y --no-install-recommends \
    build-essential \
    && rm -rf /var/lib/apt/lists/*

COPY requirements.txt .
RUN pip install --no-cache-dir --prefix=/install -r requirements.txt

# Stage 2: Runtime
FROM python:3.12-slim

WORKDIR /app
ENV PYTHONDONTWRITEBYTECODE=1
ENV PYTHONUNBUFFERED=1

# Copy only installed packages
COPY --from=builder /install /usr/local

# Copy application code
COPY ./src ./src
COPY ./config ./config

# Security: Run as non-root
RUN useradd -m chiwi && chown -R chiwi:chiwi /app
USER chiwi

EXPOSE 8000

# Honor $PORT (Cloud Run injects 8080); default to 8000 for local/docker-compose.
CMD exec uvicorn src.main:app --host 0.0.0.0 --port ${PORT:-8000}
