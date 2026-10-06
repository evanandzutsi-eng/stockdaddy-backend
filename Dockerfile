# =========================================================================
# NGX INTELLIGENCE TERMINAL - BACKEND PRODUCTION DOCKERFILE
# =========================================================================
# Multi-stage build optimized for minimal image size, security, and 
# fast deployment on DigitalOcean Droplets.

# --------------------------------------------------------------------------
# STAGE 1: BUILDER (Compile dependencies)
# --------------------------------------------------------------------------
FROM python:3.11-slim AS builder

WORKDIR /app

# Install system dependencies required for building Python C-extensions 
# (e.g., psycopg2 for PostgreSQL, cryptography for JWT)
RUN apt-get update && apt-get install -y --no-install-recommends \
    build-essential \
    libpq-dev \
    && rm -rf /var/lib/apt/lists/*

COPY requirements.txt .

# Build wheels without cache to keep the builder layer clean
RUN pip wheel --no-cache-dir --no-deps --wheel-dir /app/wheels -r requirements.txt

# --------------------------------------------------------------------------
# STAGE 2: RUNTIME (Lean, secure production image)
# --------------------------------------------------------------------------
FROM python:3.11-slim

WORKDIR /app

# Install only the runtime system dependencies (no build tools)
RUN apt-get update && apt-get install -y --no-install-recommends \
    libpq5 \
    curl \
    && rm -rf /var/lib/apt/lists/* \
    # Cybersecurity: Create a non-root user to run the application
    && addgroup --system appgroup \
    && adduser --system --ingroup appgroup appuser

# Install pre-compiled wheels from the builder stage
COPY --from=builder /app/wheels /wheels
COPY --from=builder /app/requirements.txt .
RUN pip install --no-cache /wheels/*

# Copy application source code
COPY ./app ./app

# Cybersecurity: Switch to non-root user
USER appuser

# Expose the FastAPI port
EXPOSE 8000

# Docker Healthcheck: Ensures Cloudflare/Docker knows when the app is ready
HEALTHCHECK --interval=30s --timeout=5s --start-period=15s --retries=3 \
    CMD curl -f http://localhost:8000/health || exit 1

# Run the application using Uvicorn with 2 workers (optimized for 2GB RAM Droplet)
CMD ["uvicorn", "app.main:app", "--host", "0.0.0.0", "--port", "8000", "--workers", "2"]