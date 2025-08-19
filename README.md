# Real Estate Video Analysis API

Backend API for analyzing real estate videos using BLIP-2 AI model via RunPod serverless infrastructure.

## Overview

This backend orchestrates AI-powered video analysis for real estate properties:
- **FastAPI** backend for job management and API endpoints
- **RunPod** serverless GPUs for BLIP-2 frame analysis
- **AWS S3** for video storage and results
- **PostgreSQL/SQLite** for job tracking

The backend contains **no ML models** - all AI processing happens on RunPod.

## Quick Start

### Prerequisites
- Python 3.11+
- [UV package manager](https://github.com/astral-sh/uv)
- [Just command runner](https://github.com/casey/just) (optional)
- AWS S3 credentials
- RunPod API key

### Installation

```bash
# Install UV
curl -LsSf https://astral.sh/uv/install.sh | sh

# Install dependencies
uv sync

# Setup environment
cp .env.example .env
# Edit .env with your credentials

# Start development server
just dev
# Or manually:
uv run python run.py
```

## Configuration

Edit `.env`:
```bash
# Database
DATABASE_URL=sqlite:///./real_estate.db  # or PostgreSQL

# AWS S3
AWS_ACCESS_KEY_ID=your_key
AWS_SECRET_ACCESS_KEY=your_secret
S3_BUCKET_VIDEOS=real-estate-videos
S3_BUCKET_RESULTS=real-estate-results

# RunPod
RUNPOD_API_KEY=your_api_key
RUNPOD_ENDPOINT_ID=your_endpoint_id

# API
DEBUG=true
CORS_ORIGINS=http://localhost:3000
```

## API Usage

### Create Analysis Job

```bash
curl -X POST "http://localhost:8000/api/v1/jobs/" \
  -H "Content-Type: multipart/form-data" \
  -F "files=@property_video.mp4" \
  -F 'property_data={"property_type": "residential", "bedrooms": 3}'
```

### Check Job Status

```bash
curl "http://localhost:8000/api/v1/jobs/{job_id}"
```

## What It Does

1. **Accepts video uploads** via REST API
2. **Stores videos** in S3
3. **Submits to RunPod** for BLIP-2 analysis
4. **RunPod extracts frames** at 3 FPS and generates:
   - Scene descriptions
   - Room type identification  
   - Feature detection
5. **Returns results** with timestamped frame descriptions

## Project Structure

```
├── main.py              # FastAPI application
├── api/                 # API endpoints
│   ├── health.py       # Health checks
│   ├── jobs.py         # Job management
│   └── webhook.py      # RunPod webhooks
├── services/           # External services
│   ├── s3_service.py   # S3 operations
│   └── runpod_service.py # RunPod client
├── database/           # Database models
├── utils/              # Configuration
└── runpod/            # RunPod container
    └── handler.py     # BLIP-2 processing
```

## Development Commands

```bash
just dev          # Start development server
just test-e2e     # Test end-to-end workflow
just s3-setup     # Create S3 buckets
just fmt          # Format code
just lint         # Lint code
just check        # Run all checks
```

## License

Private project for real estate video analysis.