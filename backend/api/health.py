"""Health check endpoints for monitoring system status."""

from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session
import time
from typing import Dict, Any

from database.connection import get_db, db_manager
from services.s3_service import s3_service
from services.runpod_service import runpod_service
from utils.config import settings

router = APIRouter()


@router.get("/")
async def health_check():
    """Basic health check endpoint."""
    return {
        "status": "healthy",
        "timestamp": time.time(),
        "service": "real-estate-video-processing"
    }


@router.get("/detailed")
async def detailed_health_check(db: Session = Depends(get_db)):
    """Detailed health check including all service dependencies."""
    
    health_status = {
        "status": "healthy",
        "timestamp": time.time(),
        "components": {}
    }
    
    # Database health
    db_health = db_manager.get_health_status()
    health_status["components"]["database"] = db_health
    
    # S3 health
    s3_health = s3_service.validate_configuration()
    health_status["components"]["s3"] = {
        "status": "healthy" if all(s3_health.values()) else "degraded",
        "details": s3_health
    }
    
    # RunPod health
    runpod_health = runpod_service.validate_configuration()
    health_status["components"]["runpod"] = {
        "status": "healthy" if all(runpod_health.values()) else "degraded",
        "details": runpod_health
    }
    
    # Overall status
    component_statuses = [
        health_status["components"]["database"]["status"],
        health_status["components"]["s3"]["status"],
        health_status["components"]["runpod"]["status"]
    ]
    
    if "unhealthy" in component_statuses:
        health_status["status"] = "unhealthy"
    elif "degraded" in component_statuses:
        health_status["status"] = "degraded"
    
    return health_status


@router.get("/readiness")
async def readiness_check():
    """Kubernetes readiness probe endpoint."""
    
    # Test critical dependencies
    try:
        # Test database connection
        if not db_manager.test_connection():
            return {"status": "not_ready", "reason": "database_unavailable"}, 503
        
        # Check required configuration
        if not settings.runpod_api_key or not settings.runpod_endpoint_id:
            return {"status": "not_ready", "reason": "runpod_not_configured"}, 503
        
        if not settings.aws_access_key_id or not settings.aws_secret_access_key:
            return {"status": "not_ready", "reason": "s3_not_configured"}, 503
        
        return {"status": "ready"}
        
    except Exception as e:
        return {"status": "not_ready", "reason": str(e)}, 503


@router.get("/liveness")
async def liveness_check():
    """Kubernetes liveness probe endpoint."""
    return {"status": "alive", "timestamp": time.time()}


@router.get("/configuration")
async def configuration_status():
    """Check configuration status without exposing sensitive values."""
    
    return {
        "database": {
            "configured": bool(settings.database_url),
            "type": "sqlite" if settings.database_url.startswith("sqlite") else "postgresql"
        },
        "s3": {
            "credentials_configured": bool(settings.aws_access_key_id and settings.aws_secret_access_key),
            "buckets_configured": bool(settings.s3_bucket_videos and settings.s3_bucket_results),
            "region": settings.aws_region
        },
        "runpod": {
            "api_key_configured": bool(settings.runpod_api_key),
            "endpoint_configured": bool(settings.runpod_endpoint_id)
        },
        "api": {
            "host": settings.api_host,
            "port": settings.api_port,
            "debug": settings.debug,
            "cors_origins": len(settings.cors_origins_list)
        }
    }