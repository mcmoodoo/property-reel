# Real Estate Video Processing Pipeline

An AI-powered system that automatically creates professional property showcase videos from raw footage. The pipeline uses a **backend-only API** for job orchestration while delegating all machine learning processing to **RunPod serverless GPUs**.

## 🏗️ Architecture Overview

```
Real Estate Agency → Web Frontend → Backend API → RunPod Serverless → Final Showcase
        ↓               ↓             ↓              ↓                    ↓
   Upload Videos    React App    FastAPI      All ML Models          S3 Storage
```

### Key Design Principles
- **Backend**: Pure API/orchestration layer (NO ML models)
- **RunPod**: All AI inference on serverless GPUs (CLIP, YOLO, NIMA, etc.)
- **Scalable**: Handle multiple concurrent processing jobs
- **Cost-effective**: Pay-per-use serverless GPU processing

## 🚀 Quick Start

### Backend Setup

```bash
# Navigate to backend directory
cd backend/

# Install dependencies with UV
uv sync

# Copy environment configuration
cp .env.example .env
# Edit .env with your credentials

# Start the API server
uv run python run.py

# Or use uvicorn directly
uv run uvicorn main:app --host 0.0.0.0 --port 8000 --reload
```

The API will be available at `http://localhost:8000` with documentation at `http://localhost:8000/docs`

### Environment Configuration

Edit `backend/.env` with your credentials:

```bash
# Database
DATABASE_URL=postgresql://user:password@localhost:5432/real_estate_pipeline

# AWS S3 (for video storage)
AWS_ACCESS_KEY_ID=your_access_key
AWS_SECRET_ACCESS_KEY=your_secret_key
S3_BUCKET_VIDEOS=real-estate-videos
S3_BUCKET_RESULTS=real-estate-results

# RunPod (for ML processing)
RUNPOD_API_KEY=your_runpod_api_key
RUNPOD_ENDPOINT_ID=your_endpoint_id

# API Configuration
DEBUG=true
CORS_ORIGINS=http://localhost:3000
```

## 📋 API Usage

### Upload Property Videos

```bash
curl -X POST "http://localhost:8000/api/v1/jobs/" \
  -H "Content-Type: multipart/form-data" \
  -F "files=@kitchen.mp4" \
  -F "files=@living_room.mp4" \
  -F "files=@exterior.mp4" \
  -F 'property_data={"property_type": "residential", "bedrooms": 3, "bathrooms": 2, "square_feet": 1500}'
```

Response:
```json
{
  "job_id": "123e4567-e89b-12d3-a456-426614174000",
  "status": "processing",
  "video_count": 3,
  "estimated_completion": "2024-01-20T15:30:00"
}
```

### Check Processing Status

```bash
curl "http://localhost:8000/api/v1/jobs/123e4567-e89b-12d3-a456-426614174000"
```

Response:
```json
{
  "job_id": "123e4567-e89b-12d3-a456-426614174000",
  "status": "completed",
  "progress": 100,
  "result_url": "https://s3.amazonaws.com/real-estate-results/showcases/final_video.mp4",
  "created_at": "2024-01-20T14:30:00",
  "completed_at": "2024-01-20T15:25:00"
}
```

## 🎯 Core Features

### 🏠 Property-Specific Processing
- **Room Classification**: Automatically identifies kitchens, bedrooms, bathrooms, exteriors
- **Quality Assessment**: Uses CLIP, NIMA, and computer vision for aesthetic scoring
- **Motion Analysis**: Detects smooth camera movements, penalizes shaky footage
- **Content Understanding**: Focuses on key property features like appliances, fixtures

### 🎬 Video Production
- **Best Shot Selection**: Identifies the most compelling moments from each room
- **Professional Editing**: Creates smooth transitions and proper pacing
- **Showcase Generation**: Combines clips into a cohesive property tour
- **Multiple Formats**: Generates clips for different platforms (social media, listings)

### ⚡ Performance & Scale
- **Fast Processing**: ~2-5 minutes for typical property (5-8 videos)
- **Serverless GPU**: Only pay for processing time, no idle costs  
- **Concurrent Jobs**: Handle multiple properties simultaneously
- **Auto-scaling**: RunPod scales based on demand

## 🏗️ Project Structure

```
real-estate-video-pipeline/
├── backend/                    # FastAPI backend (NO ML models)
│   ├── main.py                # Application entry point
│   ├── api/                   # REST API endpoints
│   │   ├── health.py          # Health monitoring
│   │   ├── jobs.py            # Job management
│   │   └── webhook.py         # RunPod callbacks
│   ├── database/              # Data persistence
│   │   ├── models.py          # SQLAlchemy models
│   │   └── connection.py      # Database setup
│   ├── services/              # External integrations
│   │   ├── s3_service.py      # AWS S3 operations
│   │   └── runpod_service.py  # RunPod API client
│   ├── utils/                 # Utilities
│   │   ├── config.py          # Configuration management
│   │   └── validation.py      # Input validation
│   ├── requirements.txt       # Lightweight dependencies
│   └── start.sh              # Startup script
├── roadmap.md                 # Complete implementation plan
└── README.md                  # This file
```

## 🔄 Processing Pipeline

1. **Upload**: Real estate agent uploads property videos via web interface
2. **Storage**: Backend stores videos in AWS S3 with metadata
3. **Job Creation**: Backend creates processing job in database
4. **RunPod Submission**: Backend submits job to RunPod serverless endpoint
5. **ML Processing**: RunPod loads all AI models and processes videos:
   - Room classification (CLIP)
   - Quality scoring (NIMA, BRISQUE)
   - Motion analysis (RAFT, I3D)
   - Object detection (YOLOv8)
   - Best shot selection
   - Video editing and composition
6. **Results Upload**: RunPod uploads final videos back to S3
7. **Webhook**: RunPod notifies backend of completion
8. **Download**: User receives links to download showcase videos

## 🤖 AI Models Used (RunPod Only)

All machine learning models run exclusively on RunPod serverless GPUs:

### Core Models
- **CLIP ViT-B/32** - Room classification and semantic understanding
- **YOLOv8** - Object detection (appliances, furniture, fixtures)
- **NIMA** - Neural Image Assessment for aesthetic quality

### Video Analysis
- **RAFT** - Optical flow for smooth motion detection
- **TransNetV2** - Shot boundary detection
- **I3D** - Video understanding for camera movement analysis

### Quality Assessment
- **BRISQUE** - No-reference image quality metrics
- **LPIPS** - Perceptual similarity for duplicate detection

## 📊 Monitoring & Health

### Health Endpoints
```bash
# Basic health check
curl http://localhost:8000/health/

# Detailed system status
curl http://localhost:8000/health/detailed

# Kubernetes probes
curl http://localhost:8000/health/readiness
curl http://localhost:8000/health/liveness
```

### System Monitoring
- Database connectivity and performance
- S3 bucket accessibility
- RunPod API status
- Processing queue metrics
- Error rates and patterns

## 🚀 Production Deployment

### Docker Support
```dockerfile
# Backend container (no GPU required)
FROM python:3.11-slim
COPY requirements.txt .
RUN pip install -r requirements.txt
COPY . .
CMD ["./start.sh"]
```

### Kubernetes Deployment
The backend includes proper health checks for Kubernetes:
- Readiness probes check dependencies
- Liveness probes monitor application health
- Graceful shutdown handling

### RunPod Serverless
- Deploy ML pipeline to RunPod once
- Backend automatically scales with demand
- Pay only for GPU processing time

## 💰 Cost Structure

### Processing Costs (Per Property)
- **RunPod GPU**: ~$0.12-0.20 per job (2-5 minutes processing)
- **S3 Storage**: ~$0.05 per job (video storage and transfer)
- **Total**: ~$0.17-0.25 per property + profit margin

### Infrastructure Costs (Monthly)
- **Backend Server**: $20-50/month (lightweight, no GPU)
- **Database**: $25-100/month (PostgreSQL)
- **S3 Storage**: Variable based on usage
- **Monitoring**: $20-50/month (optional)

## 🔗 Next Steps

See `roadmap.md` for the complete 14-week implementation plan covering:
- ✅ **Phase 1**: Backend foundation (completed)
- **Phase 2**: API development and testing
- **Phase 3**: RunPod ML pipeline implementation
- **Phase 4**: Integration and performance testing
- **Phase 5**: Frontend development
- **Phase 6**: Production deployment
- **Phase 7**: Monitoring and analytics

## 🤝 Contributing

This project follows the roadmap in `roadmap.md`. Key principles:
- Backend remains ML-free (API/orchestration only)
- All AI processing happens on RunPod
- Scalable, cost-effective architecture
- Production-ready monitoring and deployment

## 📄 License

MIT License - See LICENSE file for details

---

**Ready to revolutionize real estate video marketing with AI! 🏡✨**