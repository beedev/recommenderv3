# ============================================================================
# ESAB Recommender V2 - Production Dockerfile (FIXED)
# Multi-stage build for optimized production deployment
# ============================================================================

# Stage 1: Builder - Install dependencies
FROM python:3.11-slim as builder

# Set working directory
WORKDIR /build

# Install system dependencies required for building Python packages
RUN apt-get update && apt-get install -y --no-install-recommends \
    gcc \
    g++ \
    libpq-dev \
    && rm -rf /var/lib/apt/lists/*

# Copy requirements first (for Docker layer caching)
COPY src/backend/requirements.txt .

# Install Python dependencies to a local directory
RUN pip install --no-cache-dir --user -r requirements.txt

# ============================================================================
# Stage 2: Runtime - Production image
FROM python:3.11-slim

# Set metadata
LABEL maintainer="ESAB Recommender Team"
LABEL description="ESAB Welding Equipment Configurator - Production Backend"
LABEL version="2.0.0"

# Create non-root user for security (MOVED UP - before copying files)
RUN useradd -m -u 1000 -s /bin/bash appuser

# Set environment variables
ENV PYTHONUNBUFFERED=1 \
    PYTHONDONTWRITEBYTECODE=1 \
    PATH=/home/appuser/.local/bin:$PATH \
    # FastAPI/Uvicorn settings
    HOST=0.0.0.0 \
    PORT=8000 \
    WORKERS=4 \
    # Application directory
    APP_DIR=/app

# Install runtime system dependencies
RUN apt-get update && apt-get install -y --no-install-recommends \
    libpq5 \
    curl \
    && rm -rf /var/lib/apt/lists/*

# Set working directory
WORKDIR ${APP_DIR}

# Copy Python dependencies from builder stage to appuser's home
# FIX: Copy to /home/appuser/.local instead of /root/.local
COPY --from=builder --chown=appuser:appuser /root/.local /home/appuser/.local

# Copy application code with proper ownership
COPY --chown=appuser:appuser src/backend/ .

# Copy frontend static files with proper ownership
COPY --chown=appuser:appuser src/frontend/ ../frontend/

# Create necessary directories with proper ownership
RUN mkdir -p logs data && \
    chown -R appuser:appuser ${APP_DIR}

# Switch to non-root user
USER appuser

# Expose port
EXPOSE ${PORT}

# Health check
HEALTHCHECK --interval=30s --timeout=10s --start-period=40s --retries=3 \
    CMD curl -f http://localhost:${PORT}/health || exit 1

# Default command - can be overridden in docker-compose or docker run
CMD ["sh", "-c", "uvicorn app.main:app --host ${HOST} --port ${PORT} --workers ${WORKERS}"]
