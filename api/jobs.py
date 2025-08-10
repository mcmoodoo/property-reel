"""Job management endpoints for video processing."""

import json
import logging
import time
from datetime import datetime

from fastapi import APIRouter, Depends, File, Form, HTTPException, Request, UploadFile
from sqlalchemy.orm import Session

from database.connection import get_db
from database.models import JobMetrics, ProcessingJob
from services.runpod_service import runpod_service
from services.s3_service import s3_service
from utils.validation import (
    JobResponse,
    JobStatus,
    PropertyData,
    validate_job_id,
    validate_video_files,
)

logger = logging.getLogger(__name__)
router = APIRouter()


@router.post("/", response_model=JobResponse)
async def create_processing_job(
    request: Request,
    files: list[UploadFile] = File(..., description="Video files to process"),
    property_data: str = Form(..., description="JSON string of property metadata"),
    db: Session = Depends(get_db),
):
    """Create a new video processing job."""

    start_time = time.time()

    try:
        # Parse property data
        try:
            property_dict = json.loads(property_data)
            property_model = PropertyData(**property_dict)
        except (json.JSONDecodeError, ValueError) as e:
            raise HTTPException(
                status_code=400, detail=f"Invalid property data: {str(e)}"
            )

        # Validate video files
        validation_errors = validate_video_files(files)
        if validation_errors:
            raise HTTPException(status_code=400, detail={"errors": validation_errors})

        # Create job record
        job = ProcessingJob.create_from_property_data(
            property_data=property_model.dict(),
            video_s3_urls=[],  # Will be updated after upload
            client_ip=request.client.host,
            user_agent=request.headers.get("user-agent"),
        )

        db.add(job)
        db.commit()
        db.refresh(job)

        logger.info(f"Created job {job.id} with {len(files)} videos")

        # Upload videos to S3
        try:
            s3_urls = await s3_service.upload_multiple_videos(files, job.id)

            # Update job with S3 URLs
            job.video_s3_urls = s3_urls
            job.video_count = len(s3_urls)
            db.commit()

            logger.info(f"Uploaded {len(s3_urls)} videos for job {job.id}")

        except Exception as e:
            # Mark job as failed and cleanup
            job.update_status("failed", f"Upload failed: {str(e)}")
            db.commit()

            logger.error(f"Upload failed for job {job.id}: {str(e)}")
            raise HTTPException(status_code=500, detail="Video upload failed")

        # Submit to RunPod
        try:
            runpod_job_id = await runpod_service.submit_job(
                video_s3_urls=s3_urls,
                property_data=property_model.dict(),
                job_id=job.id,
            )

            # Update job with RunPod info
            job.update_runpod_info(runpod_job_id, "QUEUED")
            job.update_status("processing")
            db.commit()

            logger.info(f"Submitted job {job.id} to RunPod: {runpod_job_id}")

        except Exception as e:
            # Mark job as failed
            job.update_status("failed", f"RunPod submission failed: {str(e)}")
            db.commit()

            logger.error(f"RunPod submission failed for job {job.id}: {str(e)}")
            raise HTTPException(status_code=500, detail="Processing submission failed")

        # Record upload metrics
        upload_duration = time.time() - start_time
        metrics = JobMetrics(
            job_id=job.id,
            upload_duration=upload_duration,
            total_video_size_mb=sum(
                file.size for file in files if hasattr(file, "size")
            )
            / 1024
            / 1024,
        )
        db.add(metrics)
        db.commit()

        # Calculate estimated completion (rough estimate: 2-5 minutes per video)
        estimated_minutes = len(files) * 3.5
        estimated_completion = datetime.utcnow().timestamp() + (estimated_minutes * 60)

        return JobResponse(
            job_id=job.id,
            status=job.status,
            video_count=job.video_count,
            estimated_completion=datetime.fromtimestamp(
                estimated_completion
            ).isoformat(),
        )

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Unexpected error creating job: {str(e)}")
        raise HTTPException(status_code=500, detail="Internal server error")


@router.get("/{job_id}", response_model=JobStatus)
async def get_job_status(job_id: str, db: Session = Depends(get_db)):
    """Get the status of a processing job."""

    if not validate_job_id(job_id):
        raise HTTPException(status_code=400, detail="Invalid job ID format")

    # Get job from database
    job = db.query(ProcessingJob).filter(ProcessingJob.id == job_id).first()
    if not job:
        raise HTTPException(status_code=404, detail="Job not found")

    # If job is still processing, check RunPod status
    if job.status == "processing" and job.runpod_job_id:
        try:
            runpod_status = await runpod_service.get_job_status(job.runpod_job_id)

            # Update local status based on RunPod status
            if runpod_status.get("status") == "COMPLETED":
                job.update_status("completed")
                db.commit()
            elif runpod_status.get("status") == "FAILED":
                error_msg = runpod_status.get("error", "RunPod processing failed")
                job.update_status("failed", error_msg)
                db.commit()

        except Exception as e:
            logger.error(f"Failed to check RunPod status for job {job_id}: {str(e)}")

    # Calculate progress
    progress = 0
    if job.status == "pending":
        progress = 10
    elif job.status == "processing":
        progress = 50
    elif job.status == "completed":
        progress = 100
    elif job.status == "failed":
        progress = 0

    # Get result URL if available
    result_url = None
    if job.status == "completed" and job.result_s3_urls:
        # Generate presigned URL for main results
        try:
            if "clips" in job.result_s3_urls:
                result_url = await s3_service.generate_presigned_url(
                    job.result_s3_urls["clips"][0]
                    if isinstance(job.result_s3_urls["clips"], list)
                    else job.result_s3_urls["clips"]
                )
        except Exception as e:
            logger.warning(f"Failed to generate result URL for job {job_id}: {str(e)}")

    return JobStatus(
        job_id=job.id,
        status=job.status,
        progress=progress,
        result_url=result_url,
        error_message=job.error_message,
        created_at=job.created_at.isoformat() if job.created_at else None,
        completed_at=job.completed_at.isoformat() if job.completed_at else None,
    )


@router.get("/")
async def list_jobs(
    limit: int = 50,
    offset: int = 0,
    status: str | None = None,
    db: Session = Depends(get_db),
):
    """List processing jobs with optional filtering."""

    query = db.query(ProcessingJob).order_by(ProcessingJob.created_at.desc())

    # Filter by status if provided
    if status:
        valid_statuses = ["pending", "processing", "completed", "failed"]
        if status not in valid_statuses:
            raise HTTPException(
                status_code=400, detail=f"Status must be one of: {valid_statuses}"
            )
        query = query.filter(ProcessingJob.status == status)

    # Apply pagination
    jobs = query.offset(offset).limit(min(limit, 100)).all()

    # Get total count
    total_count = query.count()

    return {
        "jobs": [job.to_dict() for job in jobs],
        "total": total_count,
        "limit": limit,
        "offset": offset,
    }


@router.delete("/{job_id}")
async def cancel_job(job_id: str, db: Session = Depends(get_db)):
    """Cancel a processing job."""

    if not validate_job_id(job_id):
        raise HTTPException(status_code=400, detail="Invalid job ID format")

    job = db.query(ProcessingJob).filter(ProcessingJob.id == job_id).first()
    if not job:
        raise HTTPException(status_code=404, detail="Job not found")

    # Can only cancel pending or processing jobs
    if job.status not in ["pending", "processing"]:
        raise HTTPException(
            status_code=400, detail=f"Cannot cancel job with status: {job.status}"
        )

    # Try to cancel RunPod job if it exists
    if job.runpod_job_id:
        try:
            cancelled = await runpod_service.cancel_job(job.runpod_job_id)
            if not cancelled:
                logger.warning(f"Failed to cancel RunPod job for {job_id}")
        except Exception as e:
            logger.error(f"Error cancelling RunPod job for {job_id}: {str(e)}")

    # Update job status
    job.update_status("failed", "Job cancelled by user")
    db.commit()

    return {"message": "Job cancelled successfully", "job_id": job_id}
