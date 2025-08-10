"""Database models for the real estate video processing pipeline."""

import uuid
from datetime import datetime
from typing import Any

from sqlalchemy import JSON, Column, DateTime, Float, Integer, String, Text
from sqlalchemy.ext.declarative import declarative_base
from sqlalchemy.sql import func

Base = declarative_base()


class ProcessingJob(Base):
    """Model for tracking video processing jobs."""

    __tablename__ = "processing_jobs"

    # Primary key
    id = Column(String, primary_key=True, default=lambda: str(uuid.uuid4()))

    # Job metadata
    status = Column(
        String, nullable=False, default="pending"
    )  # pending, processing, completed, failed
    created_at = Column(DateTime, nullable=False, default=func.now())
    updated_at = Column(
        DateTime, nullable=False, default=func.now(), onupdate=func.now()
    )
    completed_at = Column(DateTime, nullable=True)

    # Property information
    property_type = Column(String, nullable=False, default="residential")
    bedrooms = Column(Integer, nullable=True)
    bathrooms = Column(Float, nullable=True)
    square_feet = Column(Integer, nullable=True)
    price = Column(Integer, nullable=True)
    address = Column(Text, nullable=True)
    description = Column(Text, nullable=True)

    # Video processing data
    video_count = Column(Integer, nullable=False, default=0)
    video_s3_urls = Column(JSON, nullable=False, default=list)  # List of S3 URLs

    # RunPod integration
    runpod_job_id = Column(String, nullable=True)
    runpod_status = Column(String, nullable=True)

    # Processing results
    result_s3_urls = Column(
        JSON, nullable=True, default=dict
    )  # Dict of result types -> URLs
    clips_generated = Column(Integer, nullable=True, default=0)
    processing_duration = Column(Float, nullable=True)  # Duration in seconds

    # Error tracking
    error_message = Column(Text, nullable=True)
    error_details = Column(JSON, nullable=True)

    # Client information
    client_ip = Column(String, nullable=True)
    user_agent = Column(Text, nullable=True)

    def __repr__(self):
        return f"<ProcessingJob(id='{self.id}', status='{self.status}', video_count={self.video_count})>"

    def to_dict(self) -> dict[str, Any]:
        """Convert model to dictionary."""
        return {
            "job_id": self.id,
            "status": self.status,
            "created_at": self.created_at.isoformat() if self.created_at else None,
            "updated_at": self.updated_at.isoformat() if self.updated_at else None,
            "completed_at": self.completed_at.isoformat()
            if self.completed_at
            else None,
            "property_data": {
                "property_type": self.property_type,
                "bedrooms": self.bedrooms,
                "bathrooms": self.bathrooms,
                "square_feet": self.square_feet,
                "price": self.price,
                "address": self.address,
                "description": self.description,
            },
            "video_count": self.video_count,
            "runpod_job_id": self.runpod_job_id,
            "runpod_status": self.runpod_status,
            "clips_generated": self.clips_generated,
            "processing_duration": self.processing_duration,
            "error_message": self.error_message,
            "result_urls": self.result_s3_urls,
        }

    @classmethod
    def create_from_property_data(
        cls,
        property_data: dict[str, Any],
        video_s3_urls: list,
        client_ip: str | None = None,
        user_agent: str | None = None,
    ) -> "ProcessingJob":
        """Create job from property data and video URLs."""

        return cls(
            property_type=property_data.get("property_type", "residential"),
            bedrooms=property_data.get("bedrooms"),
            bathrooms=property_data.get("bathrooms"),
            square_feet=property_data.get("square_feet"),
            price=property_data.get("price"),
            address=property_data.get("address"),
            description=property_data.get("description"),
            video_count=len(video_s3_urls),
            video_s3_urls=video_s3_urls,
            client_ip=client_ip,
            user_agent=user_agent,
        )

    def update_status(self, status: str, error_message: str | None = None):
        """Update job status and timestamp."""
        self.status = status
        self.updated_at = datetime.utcnow()

        if status == "completed":
            self.completed_at = datetime.utcnow()
        elif status == "failed" and error_message:
            self.error_message = error_message

    def update_runpod_info(self, runpod_job_id: str, runpod_status: str | None = None):
        """Update RunPod job information."""
        self.runpod_job_id = runpod_job_id
        if runpod_status:
            self.runpod_status = runpod_status
        self.updated_at = datetime.utcnow()

    def update_results(
        self,
        result_urls: dict[str, Any],
        clips_count: int = 0,
        duration: float | None = None,
    ):
        """Update processing results."""
        self.result_s3_urls = result_urls
        self.clips_generated = clips_count
        if duration:
            self.processing_duration = duration
        self.updated_at = datetime.utcnow()


class JobMetrics(Base):
    """Model for tracking job processing metrics and analytics."""

    __tablename__ = "job_metrics"

    id = Column(Integer, primary_key=True, autoincrement=True)
    job_id = Column(String, nullable=False, index=True)

    # Performance metrics
    upload_duration = Column(Float, nullable=True)  # Time to upload videos
    queue_duration = Column(Float, nullable=True)  # Time waiting in queue
    processing_duration = Column(Float, nullable=True)  # RunPod processing time
    total_duration = Column(Float, nullable=True)  # Total job time

    # Video metrics
    total_video_size_mb = Column(Float, nullable=True)
    average_video_length_seconds = Column(Float, nullable=True)
    video_resolution = Column(String, nullable=True)  # e.g., "1920x1080"

    # Output metrics
    clips_extracted = Column(Integer, nullable=True, default=0)
    best_clip_score = Column(Float, nullable=True)
    average_clip_score = Column(Float, nullable=True)

    # Resource usage (if available from RunPod)
    gpu_seconds_used = Column(Float, nullable=True)
    memory_peak_mb = Column(Float, nullable=True)

    # Timestamps
    created_at = Column(DateTime, nullable=False, default=func.now())

    def __repr__(self):
        return f"<JobMetrics(job_id='{self.job_id}', clips={self.clips_extracted})>"


class SystemHealth(Base):
    """Model for tracking system health and status."""

    __tablename__ = "system_health"

    id = Column(Integer, primary_key=True, autoincrement=True)

    # System components status
    database_status = Column(String, nullable=False, default="unknown")
    s3_status = Column(String, nullable=False, default="unknown")
    runpod_status = Column(String, nullable=False, default="unknown")
    redis_status = Column(String, nullable=False, default="unknown")

    # Queue metrics
    pending_jobs = Column(Integer, nullable=False, default=0)
    processing_jobs = Column(Integer, nullable=False, default=0)
    failed_jobs_24h = Column(Integer, nullable=False, default=0)

    # Performance metrics
    average_processing_time = Column(Float, nullable=True)
    success_rate_24h = Column(Float, nullable=True)

    # Timestamp
    checked_at = Column(DateTime, nullable=False, default=func.now())

    def __repr__(self):
        return f"<SystemHealth(checked_at='{self.checked_at}', pending={self.pending_jobs})>"
