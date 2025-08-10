# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Project Overview

This is a Real Estate Video Processing Pipeline that automatically creates professional property showcase videos from raw footage. The system uses a **backend-only API architecture** where:

- **Backend**: Pure FastAPI application for job orchestration (NO ML models)
- **RunPod**: All AI/ML processing is delegated to serverless GPU infrastructure  
- **Frontend**: React web app for real estate agencies to upload videos

**Critical**: The backend contains NO machine learning models. All AI processing happens on RunPod.

## Development Commands

### Backend Development
```bash
# Navigate to backend
cd backend/

# Quick setup (installs deps + creates .env)
just setup

# Start development server
just dev

# Or manually
uv sync
cp .env.example .env  # Edit with your credentials
uv run python run.py

# Code quality
just fmt       # Format code
just lint      # Lint code  
just check     # All quality checks
just test      # Run tests

# Database (PostgreSQL in Docker)
just db-start  # Start database
just db-stop   # Stop database
```

### API Testing
```bash
# Check health
curl http://localhost:8000/health/

# Detailed health check
curl http://localhost:8000/health/detailed

# Upload property videos (example)
curl -X POST "http://localhost:8000/api/v1/jobs/" \
  -H "Content-Type: multipart/form-data" \
  -F "files=@video1.mp4" \
  -F "files=@video2.mp4" \
  -F 'property_data={"property_type": "residential", "bedrooms": 3}'
```

## Architecture Overview

### Backend-Only Design (No ML Models)
```
Frontend → Backend API → RunPod Serverless → ML Pipeline → Results
   ↓           ↓              ↓                 ↓           ↓
React      FastAPI       GPU Processing    All AI Models  S3 Storage
```

### Backend Structure (`backend/`)
- **`main.py`** - FastAPI application entry point
- **`api/`** - REST API endpoints (health, jobs, webhooks)
- **`database/`** - SQLAlchemy models and connection management
- **`services/`** - External service integrations (S3, RunPod)
- **`utils/`** - Configuration and validation utilities

### Key Components

1. **Job Management** - Track video processing jobs from upload to completion
2. **S3 Integration** - Handle video uploads and results storage
3. **RunPod Service** - Submit jobs to serverless GPU infrastructure
4. **Webhook Handler** - Receive completion notifications from RunPod
5. **Health Monitoring** - Comprehensive system health checks

### Database Models
- **ProcessingJob** - Main job tracking with property metadata
- **JobMetrics** - Performance and analytics data
- **SystemHealth** - System status monitoring

## Configuration

### Environment Variables (.env)
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
DEBUG=true
CORS_ORIGINS=http://localhost:3000
```

## API Endpoints

### Job Management
- `POST /api/v1/jobs/` - Create processing job with video uploads
- `GET /api/v1/jobs/{job_id}` - Get job status and results
- `GET /api/v1/jobs/` - List jobs with filtering
- `DELETE /api/v1/jobs/{job_id}` - Cancel processing job

### Health Monitoring
- `GET /health/` - Basic health check
- `GET /health/detailed` - Detailed dependency status
- `GET /health/readiness` - Kubernetes readiness probe
- `GET /health/liveness` - Kubernetes liveness probe

### Webhooks
- `POST /webhook/runpod/{job_id}` - RunPod completion callback

## Data Flow

1. **Upload**: Frontend uploads videos to backend API
2. **Storage**: Backend stores videos in S3
3. **Processing**: Backend submits job to RunPod serverless
4. **ML Pipeline**: RunPod runs all AI models (CLIP, YOLO, NIMA, etc.)
5. **Results**: RunPod uploads processed videos back to S3
6. **Notification**: RunPod sends webhook to backend with results
7. **Completion**: Frontend retrieves download links from backend

## Dependencies

The backend uses **lightweight dependencies only** (no ML libraries):
- **FastAPI** - REST API framework
- **SQLAlchemy** - Database ORM
- **boto3** - AWS S3 client
- **requests** - HTTP client for RunPod API
- **pydantic** - Data validation

## Development Workflow

1. **Backend Changes**: Edit backend code and test with `./start.sh`
2. **Database Changes**: Update models in `database/models.py`
3. **API Changes**: Modify endpoints in `api/` directory
4. **Testing**: Use `curl` or Postman to test API endpoints
5. **Deployment**: Deploy backend to cloud, RunPod handles ML processing

## Important Notes

- **NO ML MODELS**: The backend is pure API/orchestration only
- **RunPod Integration**: All AI processing is delegated to RunPod serverless
- **Stateless Design**: Backend doesn't store video data, only job metadata
- **Scalable Architecture**: Backend can handle multiple concurrent jobs