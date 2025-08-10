#!/usr/bin/env python3
"""Simplified RunPod handler for video stitching POC."""

import os
import json
import time
import subprocess
import traceback
from typing import Any, Dict, List
from pathlib import Path

import runpod
import boto3
import requests
import cv2
import numpy as np

# Initialize S3 client
s3_client = boto3.client(
    "s3",
    aws_access_key_id=os.environ.get("AWS_ACCESS_KEY_ID"),
    aws_secret_access_key=os.environ.get("AWS_SECRET_ACCESS_KEY"),
    region_name=os.environ.get("AWS_REGION", "us-east-1"),
)


def download_video_from_s3(s3_url: str, local_path: str) -> str:
    """Download video from S3 to local storage."""
    # Parse S3 URL (s3://bucket/key)
    parts = s3_url.replace("s3://", "").split("/", 1)
    bucket = parts[0]
    key = parts[1]

    print(f"📥 Downloading from S3: {bucket}/{key}")
    s3_client.download_file(bucket, key, local_path)
    return local_path


def get_video_info(video_path: str) -> Dict:
    """Get basic video information using OpenCV."""
    cap = cv2.VideoCapture(video_path)
    if not cap.isOpened():
        raise ValueError(f"Cannot open video: {video_path}")
    
    fps = cap.get(cv2.CAP_PROP_FPS)
    frame_count = int(cap.get(cv2.CAP_PROP_FRAME_COUNT))
    duration = frame_count / fps if fps > 0 else 0
    width = int(cap.get(cv2.CAP_PROP_FRAME_WIDTH))
    height = int(cap.get(cv2.CAP_PROP_FRAME_HEIGHT))
    
    cap.release()
    
    return {
        "duration": duration,
        "fps": fps,
        "frame_count": frame_count,
        "width": width,
        "height": height
    }


def calculate_sharpness(frame: np.ndarray) -> float:
    """Calculate frame sharpness using Laplacian variance."""
    gray = cv2.cvtColor(frame, cv2.COLOR_BGR2GRAY)
    return cv2.Laplacian(gray, cv2.CV_64F).var()


def extract_best_segment(video_path: str, segment_duration: float = 10.0) -> str:
    """Extract the best segment from middle portion of video."""
    info = get_video_info(video_path)
    
    # Focus on middle 60% of video (skip first/last 20%)
    start_offset = info["duration"] * 0.2
    end_offset = info["duration"] * 0.8
    available_duration = end_offset - start_offset
    
    # If video is shorter than segment duration, use the whole middle section
    if available_duration <= segment_duration:
        actual_duration = available_duration
        segment_start = start_offset
    else:
        # Sample frames to find sharpest section
        cap = cv2.VideoCapture(video_path)
        sample_points = []
        
        # Sample every 5 seconds in the middle section
        for t in np.arange(start_offset, end_offset, 5.0):
            cap.set(cv2.CAP_PROP_POS_MSEC, t * 1000)
            ret, frame = cap.read()
            if ret:
                sharpness = calculate_sharpness(frame)
                sample_points.append((t, sharpness))
        
        cap.release()
        
        if sample_points:
            # Find the sharpest point and center segment around it
            best_time = max(sample_points, key=lambda x: x[1])[0]
            segment_start = max(start_offset, best_time - segment_duration/2)
            segment_start = min(segment_start, end_offset - segment_duration)
            actual_duration = segment_duration
        else:
            # Fallback to middle of the middle section
            segment_start = start_offset + (available_duration - segment_duration) / 2
            actual_duration = segment_duration
    
    # Extract segment using FFmpeg
    output_path = video_path.replace('.mp4', '_segment.mp4')
    
    cmd = [
        'ffmpeg', '-y', '-i', video_path,
        '-ss', str(segment_start),
        '-t', str(actual_duration),
        '-c:v', 'libx264', '-c:a', 'aac',
        '-preset', 'fast',
        output_path
    ]
    
    result = subprocess.run(cmd, capture_output=True, text=True)
    if result.returncode != 0:
        raise Exception(f"FFmpeg failed: {result.stderr}")
    
    print(f"✂️ Extracted {actual_duration:.1f}s segment from {os.path.basename(video_path)}")
    return output_path


def concatenate_videos(video_paths: List[str], output_path: str) -> str:
    """Concatenate multiple videos into one using FFmpeg."""
    # Create a temporary file list for FFmpeg concat
    concat_file = "/tmp/concat_list.txt"
    
    with open(concat_file, 'w') as f:
        for video_path in video_paths:
            f.write(f"file '{video_path}'\n")
    
    cmd = [
        'ffmpeg', '-y', '-f', 'concat', '-safe', '0', '-i', concat_file,
        '-c:v', 'libx264', '-c:a', 'aac',
        '-preset', 'fast',
        output_path
    ]
    
    result = subprocess.run(cmd, capture_output=True, text=True)
    if result.returncode != 0:
        raise Exception(f"FFmpeg concatenation failed: {result.stderr}")
    
    print(f"🔗 Concatenated {len(video_paths)} videos into {os.path.basename(output_path)}")
    return output_path


def upload_to_s3(local_path: str, job_id: str) -> str:
    """Upload final video to S3."""
    bucket = os.environ.get("S3_BUCKET_RESULTS", "unpin-real-estate-results")
    key = f"final_videos/{job_id}_final.mp4"
    
    s3_client.upload_file(local_path, bucket, key)
    
    result_url = f"s3://{bucket}/{key}"
    print(f"📤 Uploaded final video to: {result_url}")
    
    return result_url


def process_videos(video_urls: List[str], job_id: str) -> Dict[str, Any]:
    """Process multiple videos and create final stitched video."""
    temp_dir = Path("/tmp") / job_id
    temp_dir.mkdir(exist_ok=True)
    
    segment_paths = []
    video_info = []
    
    try:
        # Process each video
        for i, video_url in enumerate(video_urls):
            print(f"🎥 Processing video {i+1}/{len(video_urls)}")
            
            # Download video
            local_video = str(temp_dir / f"video_{i}.mp4")
            download_video_from_s3(video_url, local_video)
            
            # Get video info
            info = get_video_info(local_video)
            video_info.append({
                "url": video_url,
                "duration": info["duration"],
                "resolution": f"{info['width']}x{info['height']}"
            })
            
            # Extract best segment
            if info["duration"] > 5.0:  # Only process videos longer than 5 seconds
                segment_path = extract_best_segment(local_video, segment_duration=8.0)
                segment_paths.append(segment_path)
            else:
                print(f"⚠️ Skipping short video ({info['duration']:.1f}s): {video_url}")
        
        if not segment_paths:
            raise ValueError("No suitable video segments found")
        
        # Concatenate all segments
        final_video = str(temp_dir / "final_stitched.mp4")
        concatenate_videos(segment_paths, final_video)
        
        # Upload to S3
        result_url = upload_to_s3(final_video, job_id)
        
        return {
            "status": "completed",
            "result_url": result_url,
            "processed_videos": len(segment_paths),
            "total_videos": len(video_urls),
            "video_info": video_info,
            "final_duration": sum(8.0 for _ in segment_paths)  # Each segment is ~8s
        }
        
    finally:
        # Clean up temp files
        import shutil
        if temp_dir.exists():
            shutil.rmtree(temp_dir)


def handler(job: Dict[str, Any]) -> Dict[str, Any]:
    """Main RunPod handler function."""
    try:
        print(f"🚀 Starting POC video stitching job: {job.get('id', 'unknown')}")
        start_time = time.time()

        # Extract input
        job_input = job.get("input", {})
        video_urls = job_input.get("video_urls", [])
        job_id = job_input.get("job_id", job.get("id", "unknown"))
        webhook_url = job_input.get("webhook_url")

        if not video_urls:
            raise ValueError("No video URLs provided")

        print(f"📋 Processing {len(video_urls)} videos")

        # Process videos
        result = process_videos(video_urls, job_id)
        
        # Calculate processing time
        processing_time = time.time() - start_time
        result["processing_time"] = processing_time
        result["job_id"] = job_id

        # Send webhook if provided
        if webhook_url:
            try:
                webhook_payload = {
                    "job_id": job_id,
                    "status": "COMPLETED",
                    "output": result,
                }
                requests.post(webhook_url, json=webhook_payload, timeout=10)
                print(f"✅ Webhook sent to: {webhook_url}")
            except Exception as e:
                print(f"⚠️ Failed to send webhook: {e}")

        print(f"✅ Job completed in {processing_time:.2f} seconds")
        return result

    except Exception as e:
        error_msg = f"Job failed: {str(e)}"
        print(f"❌ {error_msg}")
        print(traceback.format_exc())

        # Send failure webhook if provided
        if job_input.get("webhook_url"):
            try:
                webhook_payload = {
                    "job_id": job_input.get("job_id", "unknown"),
                    "status": "FAILED",
                    "error": error_msg,
                }
                requests.post(job_input["webhook_url"], json=webhook_payload, timeout=10)
            except:
                pass

        return {"error": error_msg, "status": "failed"}


# Start RunPod serverless worker
if __name__ == "__main__":
    print("🚀 Starting RunPod POC video stitching worker...")
    runpod.serverless.start({"handler": handler})