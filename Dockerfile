# ============================================
# CodeCraft AI - Production Docker Container
# Multi-stage build for optimized deployment
# ============================================

# ----- Stage 1: Builder -----
FROM python:3.11-slim AS builder

# Install system dependencies for building Python packages
RUN apt-get update && apt-get install -y --no-install-recommends \
    build-essential \
    curl \
    git \
    && rm -rf /var/lib/apt/lists/*

# Set working directory
WORKDIR /app

# Create virtual environment
RUN python -m venv /opt/venv
ENV PATH="/opt/venv/bin:$PATH"

# Upgrade pip and install build tools
RUN pip install --no-cache-dir --upgrade pip setuptools wheel

# Copy dependency files
COPY requirements.txt .
COPY requirements-dev.txt .

# Install production dependencies
RUN pip install --no-cache-dir -r requirements.txt

# ----- Stage 2: Runtime -----
FROM python:3.11-slim AS runtime

# Install runtime system dependencies
RUN apt-get update && apt-get install -y --no-install-recommends \
    curl \
    gnupg \
    libpq-dev \
    && rm -rf /var/lib/apt/lists/*

# Create non-root user
RUN groupadd -r appuser && useradd -r -g appuser -s /bin/bash appuser

# Copy virtual environment from builder
COPY --from=builder /opt/venv /opt/venv
ENV PATH="/opt/venv/bin:$PATH"

# Set working directory
WORKDIR /app

# Create necessary directories
RUN mkdir -p /app/logs /app/data /app/cache && \
    chown -R appuser:appuser /app

# Copy application code
COPY --chown=appuser:appuser . .

# Environment variables
ENV PYTHONUNBUFFERED=1 \
    PYTHONDONTWRITEBYTECODE=1 \
    PYTHONPATH=/app \
    PORT=8000 \
    ENVIRONMENT=production \
    LOG_LEVEL=INFO

# Expose port
EXPOSE ${PORT}

# Health check
HEALTHCHECK --interval=30s --timeout=3s --start-period=5s --retries=3 \
    CMD curl -f http://localhost:${PORT}/health || exit 1

# Switch to non-root user
USER appuser

# Run application
CMD ["gunicorn", \
    "--bind", "0.0.0.0:${PORT}", \
    "--workers", "4", \
    "--worker-class", "uvicorn.workers.UvicornWorker", \
    "--access-logfile", "-", \
    "--error-logfile", "-", \
    "--timeout", "120", \
    "--keep-alive", "5", \
    "app.main:app"]

# ----- Stage 3: Development (optional) -----
FROM runtime AS development

# Switch back to root for development dependencies
USER root

# Install development tools
RUN apt-get update && apt-get install -y --no-install-recommends \
    vim \
    htop \
    net-tools \
    && rm -rf /var/lib/apt/lists/*

# Install development Python packages
COPY --from=builder /app/requirements-dev.txt .
RUN pip install --no-cache-dir -r requirements-dev.txt

# Create entrypoint script for development
RUN echo '#!/bin/bash\n\
if [ "$ENVIRONMENT" = "development" ]; then\n\
    echo "Starting in development mode..."\n\
    uvicorn app.main:app --host 0.0.0.0 --port ${PORT:-8000} --reload\n\
else\n\
    exec "$@"\n\
fi' > /entrypoint.sh && chmod +x /entrypoint.sh

# Switch back to appuser
USER appuser

# Override CMD for development
CMD ["/entrypoint.sh"]

# ----- Stage 4: Testing -----
FROM runtime AS testing

USER root

# Install test dependencies
COPY --from=builder /app/requirements-dev.txt .
RUN pip install --no-cache-dir -r requirements-dev.txt

# Create test directory
RUN mkdir -p /app/tests && chown -R appuser:appuser /app/tests

USER appuser

# Test command
CMD ["pytest", "-v", "--cov=app", "--cov-report=term-missing", "tests/"]

# ----- Labels -----
LABEL maintainer="devops@codecraft.ai" \
      version="1.0.0" \
      description="CodeCraft AI Application Container" \
      org.label-schema.schema-version="1.0" \
      org.label-schema.name="codecraft-ai" \
      org.label-schema.vendor="CodeCraft AI" \
      org.label-schema.license="MIT" \
      org.label-schema.build-date="${BUILD_DATE}" \
      org.label-schema.vcs-url="https://github.com/codecraft-ai/app"

# ----- Build Arguments -----
ARG BUILD_DATE
ARG VERSION=1.0.0
ARG COMMIT_SHA

# ----- Metadata -----
ONBUILD LABEL org.label-schema.version="${VERSION}" \
              org.label-schema.vcs-ref="${COMMIT_SHA}"

# ----- Volume for persistent data -----
VOLUME ["/app/data", "/app/logs"]

# ----- Entrypoint for initialization -----
COPY docker-entrypoint.sh /usr/local/bin/
RUN chmod +x /usr/local/bin/docker-entrypoint.sh
ENTRYPOINT ["docker-entrypoint.sh"]
