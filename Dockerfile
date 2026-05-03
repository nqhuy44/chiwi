# Stage 1: Build
FROM python:3.12-slim AS builder

WORKDIR /app
ENV PYTHONDONTWRITEBYTECODE=1
ENV PYTHONUNBUFFERED=1

# Install build dependencies + curl (for supercronic download)
RUN apt-get update && apt-get install -y --no-install-recommends \
    build-essential \
    curl \
    tzdata \
    && rm -rf /var/lib/apt/lists/*

COPY requirements.txt .
RUN pip install --no-cache-dir --prefix=/install -r requirements.txt

# Download supercronic — container-native cron daemon (runs in foreground,
# handles signals, supports CRON_TZ per crontab file)
ARG SUPERCRONIC_VERSION=0.2.33
RUN curl -fsSL \
    "https://github.com/aptible/supercronic/releases/download/v${SUPERCRONIC_VERSION}/supercronic-linux-amd64" \
    -o /supercronic \
    && chmod +x /supercronic

# Stage 2: Runtime
FROM python:3.12-slim

WORKDIR /app
ENV PYTHONDONTWRITEBYTECODE=1
ENV PYTHONUNBUFFERED=1

# Install runtime dependencies (tzdata for timezone database)
RUN apt-get update && apt-get install -y --no-install-recommends \
    tzdata \
    && rm -rf /var/lib/apt/lists/*

# Copy only installed packages
COPY --from=builder /install /usr/local

# Copy supercronic binary
COPY --from=builder /supercronic /usr/local/bin/supercronic

# Copy application code
COPY ./src ./src
COPY ./config ./config
COPY ./cron ./cron

# Security: Run as non-root
RUN useradd -m chiwi && chown -R chiwi:chiwi /app
USER chiwi

EXPOSE 8000

# Honor $PORT (Cloud Run injects 8080); default to 8000 for local/docker-compose.
CMD exec uvicorn src.main:app --host 0.0.0.0 --port ${PORT:-8000}
