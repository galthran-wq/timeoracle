#!/bin/bash
set -e

echo "Running database migrations..."
uv run alembic upgrade head
echo "Migrations completed!"
echo "Starting server..."
exec uv run python -m src.main
