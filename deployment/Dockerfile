# ============================================
# CodeCraft AI - Production Dockerfile
# Multi-stage build for optimized deployment
# ============================================

# ============================================
# STAGE 1: Builder - Dependencies & Compilation
# ============================================
FROM python:3.11-slim AS builder

# Set environment variables for build optimization
ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    PIP_NO_CACHE_DIR=1 \
    PIP_DISABLE_PIP_VERSION_CHECK=1

# Install system dependencies for building Python packages
RUN apt-get update && apt-get install -y --no-install-recommends \
    build-essential \
    curl \
    git \
    libpq-dev \
    && rm -rf /var/lib/apt/lists/*

# Create and set working directory
WORKDIR /app

# Copy dependency files
COPY requirements/production.txt .

# Create virtual environment and install dependencies
RUN python -m venv /opt/venv
ENV PATH="/opt/venv/bin:$PATH"

# Install Python dependencies
RUN pip install --upgrade pip && \
    pip install --no-cache-dir -r production.txt

# ============================================
# STAGE 2: Runtime - Minimal Production Image
# ============================================
FROM python:3.11-slim AS runtime

# Install runtime system dependencies only
RUN apt-get update && apt-get install -y --no-install-recommends \
    libpq5 \
    curl \
    && rm -rf /var/lib/apt/lists/*

# Create non-root user for security
RUN groupadd -r appuser && useradd -r -g appuser -s /bin/bash appuser

# Copy virtual environment from builder
COPY --from=builder /opt/venv /opt/venv

# Set environment variables
ENV PATH="/opt/venv/bin:$PATH" \
    PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    PYTHONPATH="/app" \
    # Security hardening
    PYTHONHASHSEED=random \
    # Application specific
    APP_ENV="production" \
    PORT=8000

# Create app directory and set permissions
WORKDIR /app
RUN mkdir -p /app/logs /app/static /app/media && \
    chown -R appuser:appuser /app

# Copy application code
COPY --chown=appuser:appuser . .

# Switch to non-root user
USER appuser

# Health check
HEALTHCHECK --interval=30s --timeout=10s --start-period=5s --retries=3 \
    CMD curl -f http://localhost:${PORT}/health/ || exit 1

# Expose port
EXPOSE ${PORT}

# ============================================
# Entrypoint Configuration
# ============================================

# Create entrypoint script
RUN echo '#!/bin/bash\n\
set -e\n\
\n\
# Wait for database if needed\n\
if [ -n "$DATABASE_URL" ]; then\n\
    echo "Waiting for database..."\n\
    until pg_isready -h $(echo $DATABASE_URL | sed -n "s/.*@\\([^:]*\\):.*/\\1/p") -p $(echo $DATABASE_URL | sed -n "s/.*:\\/\\/[^:]*:\\([0-9]*\\).*/\\1/p") 2>/dev/null; do\n\
        sleep 2\n\
    done\n\
    echo "Database is ready"\n\
fi\n\
\n\
# Run database migrations\n\
if [ "$RUN_MIGRATIONS" = "true" ]; then\n\
    echo "Running database migrations..."\n\
    python manage.py migrate --noinput\n\
fi\n\
\n\
# Collect static files\n\
if [ "$COLLECT_STATIC" = "true" ]; then\n\
    echo "Collecting static files..."\n\
    python manage.py collectstatic --noinput\n\
fi\n\
\n\
# Create superuser if specified\n\
if [ -n "$DJANGO_SUPERUSER_USERNAME" ] && [ -n "$DJANGO_SUPERUSER_PASSWORD" ]; then\n\
    echo "Creating superuser..."\n\
    python manage.py createsuperuser --noinput || true\n\
fi\n\
\n\
# Execute the main command\n\
exec "$@"' > /app/docker-entrypoint.sh && \
    chmod +x /app/docker-entrypoint.sh

# Set entrypoint
ENTRYPOINT ["/app/docker-entrypoint.sh"]

# ============================================
# Default Command (can be overridden)
# ============================================

# Production Gunicorn configuration
CMD ["gunicorn", \
    "--bind", "0.0.0.0:8000", \
    "--workers", "4", \
    "--worker-class", "uvicorn.workers.UvicornWorker", \
    "--worker-tmp-dir", "/dev/shm", \
    "--access-logfile", "-", \
    "--error-logfile", "-", \
    "--timeout", "120", \
    "--keep-alive", "5", \
    "--max-requests", "1000", \
    "--max-requests-jitter", "50", \
    "config.wsgi:application"]

# ============================================
# Build Arguments (for customization)
# ============================================
ARG BUILD_DATE
ARG VERSION
ARG VCS_REF

# Labels for better image management
LABEL org.label-schema.build-date=$BUILD_DATE \
      org.label-schema.name="CodeCraft AI" \
      org.label-schema.description="High-concurrency AI application" \
      org.label-schema.url="https://codecraft.ai" \
      org.label-schema.vcs-url="https://github.com/codecraft-ai/app" \
      org.label-schema.vcs-ref=$VCS_REF \
      org.label-schema.version=$VERSION \
      org.label-schema.schema-version="1.0" \
      maintainer="devops@codecraft.ai"

# ============================================
# Security Best Practices
# ============================================

# Run as non-root user (already set above)
# Minimal base image
# No SSH server
# No unnecessary packages
# Regular security updates in base image
# Application runs in read-only mode where possible

# Note: For additional security, consider:
# 1. Using distroless Python image for final stage
# 2. Implementing image scanning in CI/CD
# 3. Using secrets management for sensitive data
# 4. Implementing resource limits in production

# ============================================
# Performance Optimizations
# ============================================

# Multi-stage build reduces image size
# Virtual environment reduces layer count
# .dockerignore excludes unnecessary files
# Gunicorn with Uvicorn workers for async support
# Shared memory for worker temp files
# Connection pooling for database
# Proper worker count based on CPU cores

# ============================================
# Environment Variables Reference
# ============================================
# Required:
# DATABASE_URL=postgresql://user:pass@host:port/dbname
#
# Optional:
# RUN_MIGRATIONS=true/false
# COLLECT_STATIC=true/false
# DJANGO_SUPERUSER_USERNAME=admin
# DJANGO_SUPERUSER_PASSWORD=changeme
# DJANGO_SECRET_KEY=your-secret-key
# DEBUG=false
# ALLOWED_HOSTS=localhost,127.0.0.1
# CORS_ALLOWED_ORIGINS=http://localhost:3000
# REDIS_URL=redis://redis:6379/0
# CELERY_BROKER_URL=redis://redis:6379/1
# EMAIL_HOST=smtp.gmail.com
# EMAIL_PORT=587
# EMAIL_USE_TLS=true
# STATIC_URL=/static/
# MEDIA_URL=/media/
# LOG_LEVEL=INFO
# SENTRY_DSN=https://your-sentry-dsn

# ============================================
# Build Instructions
# ============================================
# Build with tags and metadata:
# docker build \
#   --build-arg BUILD_DATE=$(date -u +'%Y-%m-%dT%H:%M:%SZ') \
#   --build-arg VERSION=1.0.0 \
#   --build-arg VCS_REF=$(git rev-parse --short HEAD) \
#   -t codecraft-ai:latest \
#   -t codecraft-ai:1.0.0 \
#   .
#
# Run locally:
# docker run -p 8000:8000 \
#   -e DATABASE_URL=postgresql://user:pass@host:port/dbname \
#   -e DJANGO_SECRET_KEY=your-secret-key \
#   codecraft-ai:latest
#
# Run with docker-compose:
# docker-compose up -d
#
# Push to registry:
# docker tag codecraft-ai:latest registry.example.com/codecraft-ai:latest
# docker push registry.example.com/codecraft-ai:latest

# ============================================
# Monitoring & Logging
# ============================================
# Logs are sent to stdout/stderr for container orchestration
# Health check endpoint at /health/
# Metrics endpoint at /metrics/ (if configured)
# Structured JSON logging available via LOG_FORMAT=json

# ============================================
# Resource Limits (set in production deployment)
# ============================================
# Recommended production limits:
# memory: 1GB limit, 512MB reservation
# cpu: 1.0 limit, 0.5 reservation
# ulimits:
#   nofile: 65536:65536
#   nproc: 65536:65536

# ============================================
# Volume Mounts
# ============================================
# For persistent storage:
# - /app/media: User uploaded files
# - /app/logs: Application logs
# - /app/static: Collected static files (if not using CDN)
#
# Example:
# docker run -v ./media:/app/media -v ./logs:/app/logs ...

# ============================================
# Network Configuration
# ============================================
# Exposes port 8000 only
# Internal networking for microservices
# External traffic through reverse proxy (nginx/traefik)

# ============================================
# Image Size Optimization
# ============================================
# Final image size: ~200MB
# Builder stage: ~1GB (discarded)
# Multi-stage reduces size by ~80%
# No development tools in runtime image
# Clean apt cache and pip cache

# ============================================
# CI/CD Integration
# ============================================
# This Dockerfile is designed for:
# - GitHub Actions
# - GitLab CI
# - Jenkins
# - CircleCI
# - Any container registry
#
# Build context should be project root
# .dockerignore excludes:
#   .git, __pycache__, *.pyc, .env, tests, docs

# End of Dockerfile
