"""Webhook endpoints for receiving RunPod job completion notifications."""

from fastapi import APIRouter, Request, HTTPException, Depends, BackgroundTasks
from sqlalchemy.orm import Session
import json
import logging
from typing import Dict, Any
import time

from database.connection import get_db
from database.models import ProcessingJob, JobMetrics
from services.s3_service import s3_service
from utils.validation import validate_job_id

logger = logging.getLogger(__name__)
router = APIRouter()


@router.post("/runpod/{job_id}")
async def runpod_webhook(
    job_id: str,
    request: Request,
    background_tasks: BackgroundTasks,
    db: Session = Depends(get_db)
):
    """Handle RunPod job completion webhook."""
    
    # Validate job ID
    if not validate_job_id(job_id):
        raise HTTPException(status_code=400, detail="Invalid job ID format")
    
    # Get job from database
    job = db.query(ProcessingJob).filter(ProcessingJob.id == job_id).first()
    if not job:
        logger.warning(f"Webhook received for unknown job: {job_id}")
        raise HTTPException(status_code=404, detail="Job not found")
    
    try:
        # Parse webhook payload
        payload = await request.json()
        
        logger.info(f"Received RunPod webhook for job {job_id}: {payload.get('status', 'unknown')}")
        
        # Process the webhook in the background
        background_tasks.add_task(
            process_runpod_webhook,
            job_id=job_id,
            payload=payload,
            db_session=db
        )
        
        return {"status": "received", "job_id": job_id}
        
    except Exception as e:
        logger.error(f"Failed to process RunPod webhook for job {job_id}: {str(e)}")
        raise HTTPException(status_code=500, detail="Webhook processing failed")


async def process_runpod_webhook(job_id: str, payload: Dict[Any, Any], db_session: Session):
    """Process RunPod webhook payload in background."""
    
    try:
        # Get job (refresh from DB since this runs in background)
        job = db_session.query(ProcessingJob).filter(ProcessingJob.id == job_id).first()
        if not job:
            logger.error(f"Job {job_id} not found during webhook processing")
            return
        
        runpod_status = payload.get("status", "UNKNOWN")
        output = payload.get("output", {})
        
        # Update RunPod status
        job.runpod_status = runpod_status
        
        if runpod_status == "COMPLETED":
            await handle_job_completion(job, output, db_session)
            
        elif runpod_status == "FAILED":
            error_message = payload.get("error", "RunPod processing failed")
            await handle_job_failure(job, error_message, db_session)
            
        else:
            # Still in progress, just update status
            job.updated_at = time.time()
            db_session.commit()
        
    except Exception as e:
        logger.error(f"Error processing webhook for job {job_id}: {str(e)}")
        
        # Mark job as failed if something went wrong
        try:
            job.update_status("failed", f"Webhook processing error: {str(e)}")
            db_session.commit()
        except Exception as commit_error:
            logger.error(f"Failed to update job status after webhook error: {commit_error}")


async def handle_job_completion(job: ProcessingJob, output: Dict[Any, Any], db: Session):
    """Handle successful job completion."""
    
    try:
        # Extract results from RunPod output
        result_urls = {}
        clips_count = 0
        processing_duration = None
        
        if "clips" in output:
            result_urls["clips"] = output["clips"]
            clips_count = len(output["clips"]) if isinstance(output["clips"], list) else 1
        
        if "thumbnails" in output:
            result_urls["thumbnails"] = output["thumbnails"]
        
        if "metadata" in output:
            result_urls["metadata"] = output["metadata"]
        
        if "contact_sheet" in output:
            result_urls["contact_sheet"] = output["contact_sheet"]
        
        if "processing_time" in output:
            processing_duration = output["processing_time"]
        
        # Update job with results
        job.update_results(
            result_urls=result_urls,
            clips_count=clips_count,
            duration=processing_duration
        )
        job.update_status("completed")
        
        # Update metrics
        metrics = db.query(JobMetrics).filter(JobMetrics.job_id == job.id).first()
        if metrics:
            metrics.processing_duration = processing_duration
            metrics.clips_extracted = clips_count
            
            if "scores" in output:
                scores = output["scores"]
                if isinstance(scores, list) and scores:
                    metrics.best_clip_score = max(scores)
                    metrics.average_clip_score = sum(scores) / len(scores)
            
            # Calculate total duration
            if metrics.upload_duration and processing_duration:
                metrics.total_duration = metrics.upload_duration + processing_duration
        
        db.commit()
        
        logger.info(f"Job {job.id} completed successfully with {clips_count} clips")
        
    except Exception as e:
        logger.error(f"Error handling job completion for {job.id}: {str(e)}")
        job.update_status("failed", f"Result processing error: {str(e)}")
        db.commit()


async def handle_job_failure(job: ProcessingJob, error_message: str, db: Session):
    """Handle job failure."""
    
    try:
        job.update_status("failed", error_message)
        
        # Update metrics
        metrics = db.query(JobMetrics).filter(JobMetrics.job_id == job.id).first()
        if metrics:
            # Calculate total duration up to failure
            if metrics.upload_duration:
                metrics.total_duration = metrics.upload_duration
        
        db.commit()
        
        logger.warning(f"Job {job.id} failed: {error_message}")
        
    except Exception as e:
        logger.error(f"Error handling job failure for {job.id}: {str(e)}")


@router.get("/test/{job_id}")
async def test_webhook(job_id: str, db: Session = Depends(get_db)):
    """Test webhook endpoint for development."""
    
    # Only available in debug mode
    from utils.config import settings
    if not settings.debug:
        raise HTTPException(status_code=404, detail="Not found")
    
    # Simulate successful completion
    test_payload = {
        "status": "COMPLETED",
        "output": {
            "clips": [
                "s3://real-estate-results/results/test-job/clips/clip_001.mp4",
                "s3://real-estate-results/results/test-job/clips/clip_002.mp4"
            ],
            "thumbnails": [
                "s3://real-estate-results/results/test-job/thumbnails/thumb_001.jpg",
                "s3://real-estate-results/results/test-job/thumbnails/thumb_002.jpg"
            ],
            "metadata": "s3://real-estate-results/results/test-job/metadata.json",
            "contact_sheet": "s3://real-estate-results/results/test-job/contact_sheet.jpg",
            "processing_time": 125.5,
            "scores": [0.85, 0.78]
        }
    }
    
    # Process webhook
    await process_runpod_webhook(job_id, test_payload, db)
    
    return {"message": "Test webhook processed", "payload": test_payload}