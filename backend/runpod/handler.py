#!/usr/bin/env python3
"""RunPod serverless handler for real estate video processing."""

import os
import json
import time
import traceback
from typing import Any, Dict, List

import runpod
import boto3
import requests
import torch
import numpy as np
from PIL import Image
import cv2

# Import ML models
from transformers import CLIPModel, CLIPProcessor, CLIPTokenizer
import torchvision.transforms as transforms

# Initialize S3 client
s3_client = boto3.client(
    's3',
    aws_access_key_id=os.environ.get('AWS_ACCESS_KEY_ID'),
    aws_secret_access_key=os.environ.get('AWS_SECRET_ACCESS_KEY'),
    region_name=os.environ.get('AWS_REGION', 'us-east-1')
)

# Global model variables (loaded once)
clip_model = None
clip_processor = None
device = None

def load_models():
    """Load ML models into memory."""
    global clip_model, clip_processor, device
    
    print("🔄 Loading ML models...")
    
    # Set device
    device = torch.device("cuda" if torch.cuda.is_available() else "cpu")
    print(f"Using device: {device}")
    
    # Load CLIP model for aesthetic scoring
    clip_model = CLIPModel.from_pretrained("openai/clip-vit-base-patch32")
    clip_processor = CLIPProcessor.from_pretrained("openai/clip-vit-base-patch32")
    clip_model.to(device)
    clip_model.eval()
    
    print("✅ Models loaded successfully")

def download_video_from_s3(s3_url: str, local_path: str) -> str:
    """Download video from S3 to local storage."""
    # Parse S3 URL (s3://bucket/key)
    parts = s3_url.replace("s3://", "").split("/", 1)
    bucket = parts[0]
    key = parts[1]
    
    print(f"📥 Downloading from S3: {bucket}/{key}")
    s3_client.download_file(bucket, key, local_path)
    
    return local_path

def extract_frames(video_path: str, fps: int = 3) -> List[np.ndarray]:
    """Extract frames from video at specified FPS."""
    frames = []
    cap = cv2.VideoCapture(video_path)
    
    if not cap.isOpened():
        raise ValueError(f"Cannot open video: {video_path}")
    
    original_fps = cap.get(cv2.CAP_PROP_FPS)
    frame_interval = int(original_fps / fps)
    
    frame_count = 0
    while True:
        ret, frame = cap.read()
        if not ret:
            break
            
        if frame_count % frame_interval == 0:
            # Convert BGR to RGB
            frame_rgb = cv2.cvtColor(frame, cv2.COLOR_BGR2RGB)
            frames.append(frame_rgb)
        
        frame_count += 1
    
    cap.release()
    print(f"📸 Extracted {len(frames)} frames")
    return frames

def calculate_aesthetic_score(frame: np.ndarray) -> float:
    """Calculate aesthetic score using CLIP."""
    # Convert numpy array to PIL Image
    image = Image.fromarray(frame)
    
    # Prepare image for CLIP
    inputs = clip_processor(images=image, return_tensors="pt")
    inputs = {k: v.to(device) for k, v in inputs.items()}
    
    # Get image features
    with torch.no_grad():
        image_features = clip_model.get_image_features(**inputs)
    
    # Simple aesthetic scoring (you can enhance this)
    # Using cosine similarity with "beautiful real estate interior" concept
    text_inputs = clip_processor(
        text=["beautiful real estate interior", "poor quality video"],
        return_tensors="pt",
        padding=True
    )
    text_inputs = {k: v.to(device) for k, v in text_inputs.items()}
    
    with torch.no_grad():
        text_features = clip_model.get_text_features(**text_inputs)
    
    # Calculate similarities
    image_features = image_features / image_features.norm(dim=-1, keepdim=True)
    text_features = text_features / text_features.norm(dim=-1, keepdim=True)
    
    similarities = (image_features @ text_features.T).squeeze()
    
    # Score is similarity to "beautiful" minus similarity to "poor quality"
    score = float(similarities[0] - similarities[1])
    
    return score

def process_video(video_url: str, job_id: str) -> Dict[str, Any]:
    """Process a single video and extract best shots."""
    # Download video
    local_video_path = f"/tmp/{job_id}_video.mp4"
    download_video_from_s3(video_url, local_video_path)
    
    # Extract frames
    frames = extract_frames(local_video_path, fps=3)
    
    # Score each frame
    scores = []
    for i, frame in enumerate(frames):
        score = calculate_aesthetic_score(frame)
        scores.append({
            "frame_index": i,
            "score": score,
            "timestamp": i / 3.0  # Since we extract at 3 FPS
        })
    
    # Find top scoring moments
    scores.sort(key=lambda x: x["score"], reverse=True)
    top_moments = scores[:5]  # Top 5 moments
    
    # Clean up
    os.remove(local_video_path)
    
    return {
        "video_url": video_url,
        "total_frames": len(frames),
        "top_moments": top_moments,
        "average_score": sum(s["score"] for s in scores) / len(scores) if scores else 0
    }

def upload_results_to_s3(results: Dict, job_id: str) -> str:
    """Upload processing results to S3."""
    bucket = os.environ.get('S3_BUCKET_RESULTS', 'unpin-real-estate-results')
    key = f"results/{job_id}/metadata.json"
    
    # Upload JSON results
    s3_client.put_object(
        Bucket=bucket,
        Key=key,
        Body=json.dumps(results, indent=2),
        ContentType='application/json'
    )
    
    result_url = f"s3://{bucket}/{key}"
    print(f"📤 Uploaded results to: {result_url}")
    
    return result_url

def handler(job: Dict[str, Any]) -> Dict[str, Any]:
    """Main RunPod handler function."""
    try:
        print(f"🚀 Starting job: {job.get('id', 'unknown')}")
        start_time = time.time()
        
        # Extract input
        job_input = job.get("input", {})
        video_urls = job_input.get("video_urls", [])
        job_id = job_input.get("job_id", job.get("id", "unknown"))
        webhook_url = job_input.get("webhook_url")
        
        if not video_urls:
            raise ValueError("No video URLs provided")
        
        # Load models if not already loaded
        if clip_model is None:
            load_models()
        
        # Process each video
        results = {
            "job_id": job_id,
            "videos_processed": [],
            "processing_time": 0,
            "status": "processing"
        }
        
        for video_url in video_urls:
            try:
                video_result = process_video(video_url, job_id)
                results["videos_processed"].append(video_result)
            except Exception as e:
                print(f"❌ Error processing video {video_url}: {e}")
                results["videos_processed"].append({
                    "video_url": video_url,
                    "error": str(e)
                })
        
        # Calculate processing time
        processing_time = time.time() - start_time
        results["processing_time"] = processing_time
        results["status"] = "completed"
        
        # Upload results to S3
        result_url = upload_results_to_s3(results, job_id)
        results["result_url"] = result_url
        
        # Send webhook if provided
        if webhook_url:
            try:
                webhook_payload = {
                    "job_id": job_id,
                    "status": "COMPLETED",
                    "output": results
                }
                requests.post(webhook_url, json=webhook_payload, timeout=10)
                print(f"✅ Webhook sent to: {webhook_url}")
            except Exception as e:
                print(f"⚠️ Failed to send webhook: {e}")
        
        print(f"✅ Job completed in {processing_time:.2f} seconds")
        return results
        
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
                    "error": error_msg
                }
                requests.post(job_input["webhook_url"], json=webhook_payload, timeout=10)
            except:
                pass
        
        return {
            "error": error_msg,
            "status": "failed"
        }

# Start RunPod serverless worker
if __name__ == "__main__":
    print("🚀 Starting RunPod serverless worker...")
    runpod.serverless.start({"handler": handler})