# Real Estate Video Processing Backend - Development Commands
# Usage: just <recipe>

# Default recipe - show available commands
default:
    @just --list

# === Quick Start ===

# Complete setup for new developers
setup:
    uv sync
    cp .env.example .env
    @echo "🚀 Setup complete! Edit .env and run 'just dev'"

# === Development ===

# Run the development server
dev:
    uv run python run.py

# Run with uvicorn directly (alternative)
serve:
    uv run uvicorn main:app --host 0.0.0.0 --port 8000 --reload

# === Code Quality ===

# Format code with ruff
fmt:
    uv run ruff format .

# Check code quality
lint:
    uv run ruff check .

# Fix auto-fixable linting issues
fix:
    uv run ruff check . --fix

# Type checking with mypy
typecheck:
    uv run mypy .

# Run all quality checks
check: lint typecheck
    @echo "✅ All quality checks passed!"

# === Testing ===

# Run tests
test:
    uv run pytest tests/

# Run tests with coverage
test-cov:
    uv run pytest --cov=. tests/

# Test end-to-end API workflow
test-e2e:
    uv run python test_api_e2e.py

# Test RunPod connection
test-runpod:
    uv run python test_runpod_connection.py

# === S3 Management ===

# Create S3 buckets if they don't exist
s3-setup:
    uv run python -c "import asyncio; from services.s3_service import s3_service; asyncio.run(s3_service.setup_buckets())"

# Test S3 connectivity and all operations
test-s3:
    uv run python test_s3.py
    uv run python test_upload.py
    uv run python test_download.py
    uv run python test_s3_validation.py
    @echo "🎉 All S3 tests completed!"

# === Database Management ===

# Start PostgreSQL in Podman
db-start:
    podman run --name real-estate-postgres \
        -e POSTGRES_DB=real_estate_pipeline \
        -e POSTGRES_USER=postgres \
        -e POSTGRES_PASSWORD=postgres \
        -p 5432:5432 \
        -d postgres:15

# Stop PostgreSQL container
db-stop:
    podman stop real-estate-postgres

# Remove PostgreSQL container
db-remove:
    podman rm real-estate-postgres

# Reset database (stop, remove, start fresh)
db-reset: db-stop db-remove db-start
    @echo "🔄 Database reset complete"

# Connect to PostgreSQL database
db-connect:
    podman exec -it real-estate-postgres psql -U postgres -d real_estate_pipeline

# === Database Migrations ===

# Create a new migration
migrate-create MESSAGE:
    uv run alembic revision --autogenerate -m "{{MESSAGE}}"

# Apply migrations
migrate-up:
    uv run alembic upgrade head

# Rollback last migration
migrate-down:
    uv run alembic downgrade -1

# Show current migration
migrate-current:
    uv run alembic current

# === Environment & Configuration ===

# Check environment configuration
env-check:
    uv run python -c "from utils.config import settings; print('✅ Environment loaded successfully')"

# Show configuration status (without secrets)
config:
    uv run python -c "import json; from utils.config import settings; config = {'database': bool(settings.database_url), 'redis': bool(settings.redis_url), 's3_configured': bool(settings.aws_access_key_id and settings.aws_secret_access_key), 'runpod_configured': bool(settings.runpod_api_key and settings.runpod_endpoint_id), 'debug': settings.debug, 'api_port': settings.api_port}; print(json.dumps(config, indent=2))"

# === Health Checks ===

# Check API health (requires running server)
health:
    curl -s http://localhost:8000/health/ | python -m json.tool

# Check detailed health status
health-detailed:
    curl -s http://localhost:8000/health/detailed | python -m json.tool

# === RunPod Container Management ===

# Build RunPod container
runpod-build:
    #!/bin/bash
    echo "🐳 Building RunPod container..."
    cd runpod && podman build -t real-estate-processor:latest .
    echo "✅ Container built successfully"

# Deploy to GitHub Container Registry
ghcr-deploy GITHUB_USERNAME: runpod-build
    #!/bin/bash
    echo "🚀 Deploying to GitHub Container Registry..."
    
    # Tag for GHCR
    podman tag real-estate-processor:latest ghcr.io/{{GITHUB_USERNAME}}/real-estate-processor:latest
    
    # Push to GHCR
    echo "📤 Pushing to ghcr.io/{{GITHUB_USERNAME}}/real-estate-processor..."
    podman push ghcr.io/{{GITHUB_USERNAME}}/real-estate-processor:latest
    
    echo "✅ Deployment complete!"
    echo "📝 Image: ghcr.io/{{GITHUB_USERNAME}}/real-estate-processor:latest"

# Test container locally
runpod-test-local:
    #!/bin/bash
    echo "🧪 Testing RunPod container locally..."
    cd runpod && podman run --rm \
        -e AWS_ACCESS_KEY_ID="$AWS_ACCESS_KEY_ID" \
        -e AWS_SECRET_ACCESS_KEY="$AWS_SECRET_ACCESS_KEY" \
        -e AWS_REGION="us-east-1" \
        -e S3_BUCKET_VIDEOS="unpin-real-estate-videos" \
        -e S3_BUCKET_RESULTS="unpin-real-estate-results" \
        real-estate-processor:latest \
        python -c "import handler; print('✅ Handler imports successfully')"

# === RunPod Endpoint Management ===

# Interactive RunPod setup
runpod-setup:
    uv run python setup_runpod.py setup

# List RunPod endpoints
runpod-endpoints:
    #!/bin/bash
    if [ -z "$RUNPOD_API_KEY" ]; then
        echo "❌ RUNPOD_API_KEY environment variable not set"
        exit 1
    fi
    
    echo "🚀 Listing RunPod endpoints..."
    curl -s -X GET "https://rest.runpod.io/v1/endpoints" \
        -H "Authorization: Bearer $RUNPOD_API_KEY" \
        -H "Content-Type: application/json" | python -m json.tool

# Get RunPod endpoint status
runpod-status ENDPOINT_ID:
    #!/bin/bash
    if [ -z "$RUNPOD_API_KEY" ]; then
        echo "❌ RUNPOD_API_KEY environment variable not set"
        exit 1
    fi
    
    echo "🔍 Getting endpoint details for {{ENDPOINT_ID}}..."
    curl -X GET "https://rest.runpod.io/v1/endpoints/{{ENDPOINT_ID}}" \
        -H "Authorization: Bearer $RUNPOD_API_KEY" \
        -H "Content-Type: application/json" | python -m json.tool

# === Cleanup ===

# Clean Python cache files
clean:
    find . -type f -name "*.pyc" -delete
    find . -type d -name "__pycache__" -delete
    find . -type d -name "*.egg-info" -exec rm -rf {} +

# Clean everything (cache + dependencies)
clean-all: clean
    rm -rf .venv/
    rm -f uv.lock