# Backend Dockerfile for Werewolf AI Game
FROM python:3.12-slim

# Set working directory
WORKDIR /app

# Set environment variables
ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    PIP_NO_CACHE_DIR=1 \
    PIP_DISABLE_PIP_VERSION_CHECK=1

# Install system dependencies
RUN apt-get update && apt-get install -y --no-install-recommends \
    curl \
    && rm -rf /var/lib/apt/lists/*

# Copy requirements first for better caching
COPY requirements.txt .

# Install Python dependencies
RUN pip install --no-cache-dir -r requirements.txt

# Copy application code
COPY . .

# Copy and make entrypoint script executable (before switching user)
COPY entrypoint.sh /usr/local/bin/entrypoint.sh
RUN chmod +x /usr/local/bin/entrypoint.sh

# Create non-root user for security and pre-create data directory
# Use fixed UID=1000 for predictable volume permissions
# On host, run: sudo chown -R 1000:1000 ./data
RUN mkdir -p /app/data && \
    adduser --disabled-password --gecos '' --uid 1000 appuser && \
    chown -R appuser:appuser /app

USER appuser

# Expose port
EXPOSE 8000

# Health check
HEALTHCHECK --interval=30s --timeout=10s --start-period=5s --retries=3 \
    CMD curl -f http://localhost:8000/health || exit 1

# Set entrypoint to run migrations before starting the app
ENTRYPOINT ["/usr/local/bin/entrypoint.sh"]

# T-STAB-006: Run with single worker only
# IMPORTANT: Game state is stored in-memory (GameStore), so multi-worker/multi-instance
# deployment will cause game state inconsistency. Do NOT increase --workers or scale replicas.
# For production scalability, game state must be externalized to Redis/DB first.
CMD ["uvicorn", "app.main:app", "--host", "0.0.0.0", "--port", "8000", "--workers", "1"]
