"""Main FastAPI application for real estate video processing pipeline."""

from fastapi import FastAPI, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.middleware.trustedhost import TrustedHostMiddleware
from fastapi.responses import JSONResponse
import logging
import time
from contextlib import asynccontextmanager

from utils.config import settings
from database.connection import db_manager
from api import health, jobs, webhook


# Configure logging
logging.basicConfig(
    level=logging.INFO if not settings.debug else logging.DEBUG,
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
)
logger = logging.getLogger(__name__)


@asynccontextmanager
async def lifespan(app: FastAPI):
    """Application lifespan events."""

    # Startup
    logger.info("Starting Real Estate Video Processing API")

    try:
        # Initialize database tables
        db_manager.create_tables()
        logger.info("Database initialization completed")

        # Test database connection
        if db_manager.test_connection():
            logger.info("Database connection verified")
        else:
            logger.warning("Database connection test failed")

        # Log configuration status
        logger.info(f"API starting on {settings.api_host}:{settings.api_port}")
        logger.info(f"Debug mode: {settings.debug}")
        logger.info(f"CORS origins: {settings.cors_origins_list}")

        yield

    except Exception as e:
        logger.error(f"Startup failed: {str(e)}")
        raise

    # Shutdown
    logger.info("Shutting down API")


# Create FastAPI application
app = FastAPI(
    title="Real Estate Video Processing API",
    description="Backend API for processing real estate videos with AI-powered highlight extraction",
    version="1.0.0",
    docs_url="/docs" if settings.debug else None,
    redoc_url="/redoc" if settings.debug else None,
    lifespan=lifespan,
)


# Middleware setup
app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.cors_origins_list,
    allow_credentials=True,
    allow_methods=["GET", "POST", "PUT", "DELETE"],
    allow_headers=["*"],
)

# Security middleware
if not settings.debug:
    app.add_middleware(
        TrustedHostMiddleware,
        allowed_hosts=["*"],  # Configure based on your domain
    )


# Request timing middleware
@app.middleware("http")
async def add_process_time_header(request: Request, call_next):
    """Add processing time to response headers."""
    start_time = time.time()
    response = await call_next(request)
    process_time = time.time() - start_time
    response.headers["X-Process-Time"] = str(process_time)
    return response


# Global exception handler
@app.exception_handler(Exception)
async def global_exception_handler(request: Request, exc: Exception):
    """Handle unexpected errors."""
    logger.error(f"Unhandled error on {request.method} {request.url}: {str(exc)}")

    return JSONResponse(
        status_code=500,
        content={
            "error": "Internal server error",
            "detail": "An unexpected error occurred"
            if not settings.debug
            else str(exc),
            "path": str(request.url.path),
        },
    )


# Include routers
app.include_router(health.router, prefix="/health", tags=["Health"])
app.include_router(jobs.router, prefix="/api/v1/jobs", tags=["Jobs"])
app.include_router(webhook.router, prefix="/webhook", tags=["Webhooks"])


@app.get("/")
async def root():
    """Root endpoint."""
    return {
        "service": "Real Estate Video Processing API",
        "version": "1.0.0",
        "status": "operational",
        "docs": "/docs" if settings.debug else "Documentation disabled in production",
    }


@app.get("/status")
async def status():
    """Quick status check."""
    return {"status": "ok", "timestamp": time.time(), "debug_mode": settings.debug}


if __name__ == "__main__":
    import uvicorn

    uvicorn.run(
        "main:app",
        host=settings.api_host,
        port=settings.api_port,
        reload=settings.debug,
        log_level="debug" if settings.debug else "info",
    )
