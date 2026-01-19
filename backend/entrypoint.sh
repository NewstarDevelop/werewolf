#!/bin/sh
# Entrypoint script for werewolf-backend container
# Executes database migrations before starting the FastAPI server

set -e

echo "===================================="
echo "Werewolf Backend Container Starting"
echo "===================================="

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
