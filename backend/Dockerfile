# ============================================
# PRODUCTION DOCKERFILE FOR HIGH-CONCURRENCY BACKEND
# Multi-stage build for optimized deployment
# ============================================

# ---------- STAGE 1: Builder ----------
FROM python:3.11-slim AS builder

# Install system dependencies for building Python packages
RUN apt-get update && apt-get install -y --no-install-recommends \
    gcc \
    g++ \
    libpq-dev \
    curl \
    && rm -rf /var/lib/apt/lists/*

# Set working directory
WORKDIR /app

# Create virtual environment
RUN python -m venv /opt/venv
ENV PATH="/opt/venv/bin:$PATH"

# Upgrade pip and install build tools
RUN pip install --no-cache-dir --upgrade pip setuptools wheel

# Copy dependency files
COPY requirements/production.txt .

# Install Python dependencies
RUN pip install --no-cache-dir -r production.txt

# ---------- STAGE 2: Runtime ----------
FROM python:3.11-slim AS runtime

# Install runtime system dependencies
RUN apt-get update && apt-get install -y --no-install-recommends \
    libpq5 \
    curl \
    netcat-openbsd \
    && rm -rf /var/lib/apt/lists/*

# Create non-root user
RUN groupadd -r appuser && useradd -r -g appuser -s /bin/bash appuser

# Copy virtual environment from builder
COPY --from=builder /opt/venv /opt/venv
ENV PATH="/opt/venv/bin:$PATH"

# Set working directory
WORKDIR /app

# Copy application code
COPY --chown=appuser:appuser . .

# Create necessary directories with proper permissions
RUN mkdir -p /app/logs /app/static /app/media \
    && chown -R appuser:appuser /app/logs /app/static /app/media

# Switch to non-root user
USER appuser

# Environment variables
ENV PYTHONUNBUFFERED=1 \
    PYTHONDONTWRITEBYTECODE=1 \
    PYTHONPATH=/app \
    DJANGO_SETTINGS_MODULE=config.settings.production

# Health check
HEALTHCHECK --interval=30s --timeout=3s --start-period=5s --retries=3 \
    CMD curl -f http://localhost:8000/health/ || exit 1

# Expose port
EXPOSE 8000

# Default command (can be overridden)
CMD ["gunicorn", "config.wsgi:application", "--bind", "0.0.0.0:8000", "--workers", "4", "--threads", "2", "--worker-class", "gthread", "--access-logfile", "-", "--error-logfile", "-", "--log-level", "info"]

# ---------- STAGE 3: Development (optional) ----------
# This stage is for development builds only
FROM python:3.11-slim AS development

# Install development dependencies
RUN apt-get update && apt-get install -y --no-install-recommends \
    gcc \
    g++ \
    libpq-dev \
    curl \
    vim \
    postgresql-client \
    && rm -rf /var/lib/apt/lists/*

# Create virtual environment
WORKDIR /app
RUN python -m venv /opt/venv
ENV PATH="/opt/venv/bin:$PATH"

# Copy dependency files
COPY requirements/development.txt .

# Install Python dependencies
RUN pip install --no-cache-dir --upgrade pip \
    && pip install --no-cache-dir -r development.txt

# Copy application code
COPY . .

# Create non-root user for development
RUN groupadd -r devuser && useradd -r -g devuser -s /bin/bash devuser \
    && chown -R devuser:devuser /app

USER devuser

# Environment variables for development
ENV PYTHONUNBUFFERED=1 \
    PYTHONPATH=/app \
    DJANGO_SETTINGS_MODULE=config.settings.development

EXPOSE 8000

# Development server command
CMD ["python", "manage.py", "runserver", "0.0.0.0:8000"]

# ---------- STAGE 4: Celery Worker ----------
FROM runtime AS celery-worker

# Install additional dependencies for Celery
USER root
RUN apt-get update && apt-get install -y --no-install-recommends \
    redis-tools \
    && rm -rf /var/lib/apt/lists/*
USER appuser

# Celery worker command
CMD ["celery", "-A", "config.celery_app", "worker", "--loglevel=info", "--concurrency=4"]

# ---------- STAGE 5: Celery Beat ----------
FROM runtime AS celery-beat

# Celery beat scheduler command
CMD ["celery", "-A", "config.celery_app", "beat", "--loglevel=info", "--scheduler", "django_celery_beat.schedulers:DatabaseScheduler"]

# ---------- BUILD ARGUMENTS ----------
# Available build arguments for customization
ARG BUILD_VERSION=1.0.0
ARG BUILD_DATE
ARG COMMIT_SHA

# Labels for container metadata
LABEL org.label-schema.version=${BUILD_VERSION}
LABEL org.label-schema.build-date=${BUILD_DATE}
LABEL org.label-schema.vcs-ref=${COMMIT_SHA}
LABEL org.label-schema.name="High-Concurrency Backend"
LABEL org.label-schema.description="Django-based high-concurrency backend service"
LABEL org.label-schema.vendor="CodeCraft AI"
LABEL maintainer="devops@codecraft.ai"

# ---------- VOLUMES ----------
# Define volumes for persistent data
VOLUME ["/app/logs", "/app/media", "/app/static"]

# ---------- ENTRYPOINT SCRIPT ----------
# Create entrypoint script for initialization
USER root
RUN echo '#!/bin/bash\n\
set -e\n\
\n\
# Wait for database if needed\n\
if [ -n "$DATABASE_HOST" ]; then\n\
    echo "Waiting for database at $DATABASE_HOST:$DATABASE_PORT..."\n\
    while ! nc -z $DATABASE_HOST $DATABASE_PORT; do\n\
        sleep 1\n\
    done\n\
    echo "Database is ready!"\n\
fi\n\
\n\
# Wait for Redis if needed\n\
if [ -n "$REDIS_HOST" ]; then\n\
    echo "Waiting for Redis at $REDIS_HOST:$REDIS_PORT..."\n\
    while ! nc -z $REDIS_HOST $REDIS_PORT; do\n\
        sleep 1\n\
    done\n\
    echo "Redis is ready!"\n\
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
# Execute the command passed to the container\n\
exec "$@"\n\
' > /docker-entrypoint.sh \
    && chmod +x /docker-entrypoint.sh

USER appuser
ENTRYPOINT ["/docker-entrypoint.sh"]

# ---------- SECURITY HARDENING ----------
# Security recommendations (commented for reference)
# RUN apt-get purge -y gcc g++ && apt-get autoremove -y
# RUN find / -type f -perm /6000 -exec chmod a-s {} \; || true
# RUN rm -rf /tmp/* /var/tmp/*
# RUN chmod 755 /app && chmod 644 /app/*.py

# ---------- PERFORMANCE OPTIMIZATIONS ----------
# Python performance optimizations
ENV PYTHONHASHSEED=random \
    PYTHONOPTIMIZE=1

# Gunicorn performance tuning (override in production)
ENV GUNICORN_CMD_ARGS="--workers=4 --threads=2 --worker-class=gthread --max-requests=1000 --max-requests-jitter=50 --timeout=30 --keep-alive=2"

# ---------- LOGGING CONFIGURATION ----------
# Ensure proper log directory permissions
RUN mkdir -p /var/log/app && chown appuser:appuser /var/log/app

# ---------- FINAL INSTRUCTIONS ----------
# To build production image:
# docker build --target runtime -t backend:latest .
#
# To build development image:
# docker build --target development -t backend:dev .
#
# To build Celery worker:
# docker build --target celery-worker -t backend-celery:latest .
#
# To build with version info:
# docker build --build-arg BUILD_VERSION=2.0.0 --build-arg BUILD_DATE=$(date -u +'%Y-%m-%dT%H:%M:%SZ') --build-arg COMMIT_SHA=$(git rev-parse HEAD) -t backend:2.0.0 .
