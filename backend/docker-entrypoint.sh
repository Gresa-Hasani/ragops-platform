#!/bin/sh
# Apply database migrations before starting the API.
# Set RAGOPS_RUN_MIGRATIONS=false when migrations are run as a separate deployment step.
set -eu

if [ "${RAGOPS_RUN_MIGRATIONS:-true}" = "true" ]; then
    echo "Applying database migrations..."
    alembic upgrade head
fi

exec "$@"
