# CLAUDE.md

Instructions for Claude Code when working with this repository.

## Project Overview

Real Estate Video Analysis API using BLIP-2 for AI-powered frame analysis.

**Architecture**: Backend API (FastAPI) → RunPod GPU (BLIP-2) → S3 Storage

The backend contains NO ML models - all AI processing happens on RunPod.

## Quick Commands

```bash
# Development
just dev        # Start API server
just test-e2e   # Test full pipeline

# Code quality
just fmt        # Format code
just lint       # Lint code
just check      # All checks

# Infrastructure
just s3-setup   # Create S3 buckets
just db-start   # Start PostgreSQL
```

## Core Functionality

The system does ONE thing well:
1. Accept property video uploads
2. Send to RunPod for BLIP-2 analysis
3. Return timestamped frame descriptions

BLIP-2 generates for each frame (at 3 FPS):
- Scene description
- Room type identification
- Feature detection

## Project Structure

```
├── main.py              # FastAPI app
├── api/                 # REST endpoints
├── services/           # S3 & RunPod clients
├── database/           # SQLAlchemy models
├── utils/              # Configuration
└── runpod/
    └── handler.py      # BLIP-2 processing
```

## Important Notes

- Focus on BLIP-2 video analysis only
- No other ML models or features
- Backend is pure orchestration
- All AI runs on RunPod serverless