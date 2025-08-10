#!/bin/bash

# Real Estate Video Processing Backend Startup Script

set -e

echo "=== Real Estate Video Processing Backend ==="
echo "Starting backend services..."

# Check if .env file exists
if [ ! -f ".env" ]; then
    echo "Warning: .env file not found. Copying from .env.example..."
    if [ -f ".env.example" ]; then
        cp .env.example .env
        echo "Please edit .env file with your configuration before running again."
        exit 1
    else
        echo "Error: .env.example file not found. Please create .env file manually."
        exit 1
    fi
fi

# Activate virtual environment if it exists
if [ -d "venv" ]; then
    echo "Activating virtual environment..."
    source venv/bin/activate
elif [ -d ".venv" ]; then
    echo "Activating virtual environment..."
    source .venv/bin/activate
fi

# Install dependencies if requirements.txt is newer than last install
if [ ! -f ".requirements_installed" ] || [ "requirements.txt" -nt ".requirements_installed" ]; then
    echo "Installing/updating dependencies..."
    pip install -r requirements.txt
    touch .requirements_installed
fi

# Check if database needs initialization
echo "Checking database status..."
python -c "
from database.connection import db_manager
try:
    db_manager.create_tables()
    print('Database initialized successfully')
except Exception as e:
    print(f'Database initialization failed: {e}')
    exit(1)
" || exit 1

# Run database migrations if needed (placeholder for future)
# python migrate.py

# Start the server
echo "Starting FastAPI server..."
echo "Environment: $(if [ "$DEBUG" = "true" ]; then echo "Development"; else echo "Production"; fi)"
echo "API will be available at: http://${API_HOST:-0.0.0.0}:${API_PORT:-8000}"

if [ "$DEBUG" = "true" ]; then
    echo "Debug mode enabled - API docs at: http://localhost:${API_PORT:-8000}/docs"
fi

# Use uvicorn directly with environment variables
exec python -m uvicorn main:app \
    --host "${API_HOST:-0.0.0.0}" \
    --port "${API_PORT:-8000}" \
    --reload="${DEBUG:-false}" \
    --log-level="${LOG_LEVEL:-info}" \
    --access-log