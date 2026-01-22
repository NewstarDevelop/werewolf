#!/bin/sh
# Entrypoint script for werewolf-backend container
# Executes database migrations before starting the FastAPI server

set -e

echo "===================================="
echo "Werewolf Backend Container Starting"
echo "===================================="

# Ensure data directory exists and is writable
DATA_DIR="${DATA_DIR:-/app/data}"
echo "Checking data directory: $DATA_DIR"

if [ ! -d "$DATA_DIR" ]; then
    echo "Creating data directory: $DATA_DIR"
    mkdir -p "$DATA_DIR" || {
        echo "ERROR: Cannot create data directory $DATA_DIR"
        echo "Please ensure the volume mount has correct permissions"
        exit 1
    }
fi

# Check if directory is writable
if [ ! -w "$DATA_DIR" ]; then
    echo "ERROR: Data directory $DATA_DIR is not writable"
    echo "Current user: $(id)"
    echo "Directory permissions: $(ls -la $DATA_DIR 2>/dev/null || echo 'Cannot list')"
    echo ""
    echo "To fix this, run on the host machine:"
    echo "  sudo chown -R 1000:1000 ./data"
    echo "  # or"
    echo "  chmod 777 ./data"
    exit 1
fi

echo "Data directory OK: $DATA_DIR"

# Initialize database tables first (creates base schema if not exists)
echo "Initializing database..."
python -c "from app.init_db import init_database; init_database()"
echo "Database initialization completed"

# Check if migrations are disabled
RUN_MIGRATIONS="${RUN_DB_MIGRATIONS:-true}"
if [ "$RUN_MIGRATIONS" = "true" ] || [ "$RUN_MIGRATIONS" = "1" ] || [ "$RUN_MIGRATIONS" = "yes" ]; then
    echo "Running database migrations..."

    # Execute Alembic migrations (schema upgrades)
    alembic upgrade head

    echo "Database migrations completed successfully"
else
    echo "Database migrations skipped (RUN_DB_MIGRATIONS=$RUN_MIGRATIONS)"
fi

echo "Starting FastAPI application..."
echo "===================================="

# Start the application (exec replaces shell process with uvicorn)
exec "$@"
