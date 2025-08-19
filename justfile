# Property Reel - AI Video Analysis Backend
# Usage: just <recipe>

# Default recipe - show available commands
default:
    @just --list

# === Development ===

# Run the development server
dev:
    uv run python run.py

# === Code Quality ===

# Format code with ruff
fmt:
    uv run ruff format .

# Check code quality
lint:
    uv run ruff check .

# Run all quality checks
check: lint
    @echo "✅ All quality checks passed!"

# === Testing ===

# Run tests
test:
    uv run pytest tests/

# Test end-to-end API workflow
test-e2e:
    uv run python test_api_e2e.py

# Test RunPod directly with a sample video
test-runpod-direct:
    #!/bin/bash
    # Load environment variables from .env file
    if [ -f .env ]; then
        export $(grep -v '^#' .env | xargs)
    else
        echo "Error: .env file not found"
        exit 1
    fi
    
    if [ -z "$RUNPOD_API_KEY" ]; then
        echo "Error: RUNPOD_API_KEY not found in .env file"
        exit 1
    fi
    if [ -z "$RUNPOD_ENDPOINT_ID" ]; then
        echo "Error: RUNPOD_ENDPOINT_ID not found in .env file"
        exit 1
    fi
    
    echo "Triggering RunPod endpoint: $RUNPOD_ENDPOINT_ID"
    
    curl -X POST "https://api.runpod.ai/v2/$RUNPOD_ENDPOINT_ID/run" \
        -H "Authorization: Bearer $RUNPOD_API_KEY" \
        -H "Content-Type: application/json" \
        -d '{
            "input": {
                "video_urls": ["s3://unpin-real-estate-videos/test-property-video.mp4"],
                "job_id": "test-'$(date +%s)'",
                "target_fps": 3.0
            }
        }' | jq .

# Check status of a RunPod job
runpod-status JOB_ID:
    #!/bin/bash
    # Load environment variables from .env file
    if [ -f .env ]; then
        export $(grep -v '^#' .env | xargs)
    else
        echo "Error: .env file not found"
        exit 1
    fi
    
    if [ -z "$RUNPOD_API_KEY" ]; then
        echo "Error: RUNPOD_API_KEY not found in .env file"
        exit 1
    fi
    if [ -z "$RUNPOD_ENDPOINT_ID" ]; then
        echo "Error: RUNPOD_ENDPOINT_ID not found in .env file"
        exit 1
    fi
    
    echo "Checking status for job: {{JOB_ID}}"
    
    curl -X GET "https://api.runpod.ai/v2/$RUNPOD_ENDPOINT_ID/status/{{JOB_ID}}" \
        -H "Authorization: Bearer $RUNPOD_API_KEY" \
        -H "Content-Type: application/json" | jq .

# === S3 Management ===

# Create S3 buckets if they don't exist
s3-setup:
    uv run python -c "import asyncio; from services.s3_service import s3_service; asyncio.run(s3_service.setup_buckets())"

# === Database ===

# Show current migration status
migrate-current:
    uv run alembic current




# === Cleanup ===

# Clean Python cache files
clean:
    find . -type f -name "*.pyc" -delete
    find . -type d -name "__pycache__" -delete
    find . -type d -name "*.egg-info" -exec rm -rf {} +
