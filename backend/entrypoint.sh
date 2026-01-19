#!/bin/sh
# Entrypoint script for werewolf-backend container
# Executes database migrations before starting the FastAPI server

set -e

echo "===================================="
echo "Werewolf Backend Container Starting"
echo "===================================="

# Check if migrations are disabled
RUN_MIGRATIONS="${RUN_DB_MIGRATIONS:-true}"
if [ "$RUN_MIGRATIONS" = "true" ] || [ "$RUN_MIGRATIONS" = "1" ] || [ "$RUN_MIGRATIONS" = "yes" ]; then
    echo "Running database migrations..."

    # Execute Alembic migrations
    alembic upgrade head

    echo "Database migrations completed successfully"
else
    echo "Database migrations skipped (RUN_DB_MIGRATIONS=$RUN_MIGRATIONS)"
fi

echo "Starting FastAPI application..."
echo "===================================="

# Start the application (exec replaces shell process with uvicorn)
exec "$@"
