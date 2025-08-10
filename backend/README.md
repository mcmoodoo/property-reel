# Real Estate Video Processing Backend

Backend API for processing real estate videos with AI-powered highlight extraction using RunPod serverless infrastructure.

## Architecture Overview

This backend serves as the orchestration layer for a real estate video processing pipeline:

- **FastAPI** - REST API for job management
- **PostgreSQL/SQLite** - Job tracking and metrics storage  
- **AWS S3** - Video upload and results storage
- **RunPod** - Serverless GPU processing (all ML inference happens here)
- **Redis** - Caching and session management

**Important**: This backend contains NO machine learning models. All AI processing is delegated to RunPod serverless functions.

## Quick Start

### Prerequisites

- Python 3.11+
- [UV package manager](https://github.com/astral-sh/uv)
- PostgreSQL (optional, SQLite works for development)

### Installation

1. **Install UV (if not already installed):**
   ```bash
   curl -LsSf https://astral.sh/uv/install.sh | sh
   # or
   pip install uv
   ```

2. **Clone and setup:**
   ```bash
   cd backend/
   
   # Install dependencies with UV
   uv sync
   
   # Copy environment configuration
   cp .env.example .env
   # Edit .env with your credentials
   ```

3. **Start the server:**
   ```bash
   # Using UV run
   uv run python run.py
   
   # Or activate venv and run directly
   source .venv/bin/activate  # On Windows: .venv\Scripts\activate
   python run.py
   
   # Or use uvicorn directly
   uv run uvicorn main:app --host 0.0.0.0 --port 8000 --reload
   ```

## Configuration

Edit `.env` file with your configuration:

```bash
# Database
DATABASE_URL=postgresql://user:password@localhost:5432/real_estate_pipeline
REDIS_URL=redis://localhost:6379/0

# AWS S3
AWS_ACCESS_KEY_ID=your_access_key
AWS_SECRET_ACCESS_KEY=your_secret_key
S3_BUCKET_VIDEOS=real-estate-videos
S3_BUCKET_RESULTS=real-estate-results

# RunPod
RUNPOD_API_KEY=your_runpod_api_key
RUNPOD_ENDPOINT_ID=your_endpoint_id

# API Configuration
DEBUG=true  # Set to false in production
CORS_ORIGINS=http://localhost:3000,https://yourdomain.com
```

## API Endpoints

### Job Management

- `POST /api/v1/jobs/` - Create processing job with video uploads
- `GET /api/v1/jobs/{job_id}` - Get job status and results
- `GET /api/v1/jobs/` - List jobs with filtering
- `DELETE /api/v1/jobs/{job_id}` - Cancel processing job

### Health Monitoring

- `GET /health/` - Basic health check
- `GET /health/detailed` - Detailed health check with dependencies
- `GET /health/readiness` - Kubernetes readiness probe
- `GET /health/liveness` - Kubernetes liveness probe

### Webhooks

- `POST /webhook/runpod/{job_id}` - RunPod completion webhook

## Usage Example

### Creating a Processing Job

```bash
curl -X POST "http://localhost:8000/api/v1/jobs/" \
  -H "Content-Type: multipart/form-data" \
  -F "files=@property_video1.mp4" \
  -F "files=@property_video2.mp4" \
  -F 'property_data={"property_type": "residential", "bedrooms": 3, "bathrooms": 2, "square_feet": 1500, "address": "123 Main St"}'
```

Response:
```json
{
  "job_id": "123e4567-e89b-12d3-a456-426614174000",
  "status": "processing",
  "video_count": 2,
  "estimated_completion": "2024-01-20T15:30:00"
}
```

### Checking Job Status

```bash
curl "http://localhost:8000/api/v1/jobs/123e4567-e89b-12d3-a456-426614174000"
```

Response:
```json
{
  "job_id": "123e4567-e89b-12d3-a456-426614174000",
  "status": "completed",
  "progress": 100,
  "result_url": "https://s3.amazonaws.com/...",
  "created_at": "2024-01-20T14:30:00",
  "completed_at": "2024-01-20T15:25:00"
}
```

## Project Structure

```
backend/
├── main.py              # FastAPI application entry point
├── requirements.txt     # Python dependencies (no ML libraries)
├── start.sh            # Startup script
├── .env.example        # Environment configuration template
├── api/                # API endpoints
│   ├── health.py       # Health check endpoints
│   ├── jobs.py         # Job management endpoints
│   └── webhook.py      # RunPod webhook handlers
├── database/           # Database layer
│   ├── models.py       # SQLAlchemy models
│   └── connection.py   # Database connection management
├── services/           # External service integrations
│   ├── s3_service.py   # AWS S3 operations
│   └── runpod_service.py # RunPod API client
└── utils/              # Utilities
    ├── config.py       # Configuration management
    └── validation.py   # Input validation
```

## Development

### Development Setup

```bash
# Install with dev dependencies
uv sync --all-extras

# Or just dev tools
uv pip install -e ".[dev]"
```

### Code Quality

```bash
# Format code
uv run black .

# Lint code
uv run ruff check .

# Type checking
uv run mypy .
```

### Running Tests

```bash
# Install test dependencies (included in dev)
uv sync --all-extras

# Run tests
uv run pytest tests/

# With coverage
uv run pytest --cov=. tests/
```

### Database Migrations

For production deployments, use Alembic for database migrations:

```bash
# Install Alembic
uv pip install -e ".[migrations]"

# Initialize migrations
uv run alembic init alembic

# Create migration
uv run alembic revision --autogenerate -m "Initial tables"

# Apply migrations
uv run alembic upgrade head
```

### Health Monitoring

The API provides comprehensive health checks:

- Database connectivity
- S3 bucket access
- RunPod API connectivity
- Configuration validation

Access health dashboard: `http://localhost:8000/health/detailed`

## Production Deployment

### Docker Deployment

```dockerfile
FROM python:3.11-slim

WORKDIR /app
COPY requirements.txt .
RUN pip install -r requirements.txt

COPY . .
EXPOSE 8000

CMD ["./start.sh"]
```

### Kubernetes Deployment

The API includes readiness and liveness probes for Kubernetes:

```yaml
apiVersion: apps/v1
kind: Deployment
metadata:
  name: real-estate-api
spec:
  replicas: 3
  selector:
    matchLabels:
      app: real-estate-api
  template:
    spec:
      containers:
      - name: api
        image: real-estate-api:latest
        ports:
        - containerPort: 8000
        livenessProbe:
          httpGet:
            path: /health/liveness
            port: 8000
        readinessProbe:
          httpGet:
            path: /health/readiness
            port: 8000
```

## Security Considerations

- All file uploads are validated for type and size
- Job IDs use UUIDs to prevent enumeration
- CORS is configurable for cross-origin requests
- No sensitive data is logged in production
- Database connections use connection pooling
- API includes request timing headers

## Monitoring & Analytics

The system tracks:
- Job processing metrics
- System health status
- Performance statistics
- Error rates and patterns

Access via the database `job_metrics` and `system_health` tables.

## Troubleshooting

### Common Issues

1. **Database connection failed**
   - Check DATABASE_URL in .env
   - Ensure database server is running

2. **S3 upload errors**
   - Verify AWS credentials and bucket permissions
   - Check bucket names and regions

3. **RunPod submission failed**
   - Validate RUNPOD_API_KEY and RUNPOD_ENDPOINT_ID
   - Ensure RunPod endpoint is deployed and active

4. **Webhook not received**
   - Check WEBHOOK_BASE_URL is accessible from RunPod
   - Verify firewall and network configuration

### Debug Mode

Enable debug mode for detailed logging:

```bash
export DEBUG=true
./start.sh
```

Debug mode enables:
- Detailed SQL query logging  
- API documentation at `/docs`
- Enhanced error messages
- Test webhook endpoints

## License

This project is part of the Real Estate Video Processing Pipeline system.