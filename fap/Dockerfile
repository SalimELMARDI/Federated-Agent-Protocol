# Multi-stage build for FAP services
FROM python:3.12-slim as build

WORKDIR /app

# Install build dependencies
RUN apt-get update && apt-get install -y --no-install-recommends \
    gcc \
    postgresql-client \
    && rm -rf /var/lib/apt/lists/*

# Copy pyproject.toml and install dependencies
COPY pyproject.toml .
RUN python -m pip install --upgrade pip setuptools wheel && \
    python -m pip install -e .

# Final stage
FROM python:3.12-slim

WORKDIR /app

# Install runtime dependencies
RUN apt-get update && apt-get install -y --no-install-recommends \
    postgresql-client \
    curl \
    && rm -rf /var/lib/apt/lists/*

# Copy installed packages from build stage
COPY --from=build /usr/local/lib/python3.12/site-packages /usr/local/lib/python3.12/site-packages

# Copy the entire project
COPY . .

# Set Python path to include the app directories
ENV PYTHONPATH=/app/apps/coordinator_api/src:/app/apps/participant_docs/src:/app/apps/participant_kb/src:/app/apps/participant_logs/src:/app/packages/fap_client/src:/app/packages/fap_mcp/src:/app/packages/fap_core/src

# Create non-root user for security
RUN useradd -m -u 1000 fapuser && chown -R fapuser:fapuser /app
USER fapuser

# Default command (can be overridden)
CMD ["uvicorn", "coordinator_api.main:app", "--host", "0.0.0.0", "--port", "8000"]
