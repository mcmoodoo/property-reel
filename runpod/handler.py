#!/usr/bin/env python3
"""RunPod handler with BLIP-2 frame analysis for real estate videos."""

import os
import json
import time
import traceback
from typing import Any, Dict, List, Tuple
from pathlib import Path

import runpod
import boto3
import cv2
import torch
from PIL import Image
from transformers import Blip2Processor, Blip2ForConditionalGeneration

# Initialize S3 client
s3_client = boto3.client(
    "s3",
    aws_access_key_id=os.environ.get("AWS_ACCESS_KEY_ID"),
    aws_secret_access_key=os.environ.get("AWS_SECRET_ACCESS_KEY"),
    region_name=os.environ.get("AWS_REGION", "us-east-1"),
)

# Global model variables (loaded once)
blip_processor = None
blip_model = None
device = None


def load_blip2_model():
    """Load BLIP-2 model once at startup."""
    global blip_processor, blip_model, device

    print("🤖 Loading BLIP-2 model...")
    device = torch.device("cuda" if torch.cuda.is_available() else "cpu")
    print(f"Using device: {device}")

    # Use BLIP-2 for better descriptions
    model_name = "Salesforce/blip2-opt-2.7b"

    blip_processor = Blip2Processor.from_pretrained(model_name)
    blip_model = Blip2ForConditionalGeneration.from_pretrained(
        model_name,
        torch_dtype=torch.float16 if torch.cuda.is_available() else torch.float32,
        device_map="auto",
    )
    blip_model.eval()

    print("✅ BLIP-2 model loaded successfully")


def download_video_from_s3(s3_url: str, local_path: str) -> str:
    """Download video from S3 to local storage."""
    parts = s3_url.replace("s3://", "").split("/", 1)
    bucket = parts[0]
    key = parts[1]

    print(f"📥 Downloading from S3: {bucket}/{key}")
    s3_client.download_file(bucket, key, local_path)
    return local_path


def extract_frames_at_fps(
    video_path: str, target_fps: float = 3.0
) -> List[Tuple[float, Image.Image]]:
    """Extract frames from video at specified FPS rate."""
    frames_with_timestamps = []

    cap = cv2.VideoCapture(video_path)
    if not cap.isOpened():
        raise ValueError(f"Cannot open video: {video_path}")

    # Get video properties
    video_fps = cap.get(cv2.CAP_PROP_FPS)
    total_frames = int(cap.get(cv2.CAP_PROP_FRAME_COUNT))
    duration = total_frames / video_fps if video_fps > 0 else 0

    print(f"📹 Video info: {video_fps:.1f}fps, {duration:.1f}s, {total_frames} frames")

    # Calculate frame interval
    frame_interval = int(video_fps / target_fps)

    frame_count = 0
    extracted_count = 0

    while True:
        ret, frame = cap.read()
        if not ret:
            break

        # Extract frame at target FPS interval
        if frame_count % frame_interval == 0:
            timestamp = frame_count / video_fps

            # Convert BGR to RGB and then to PIL Image
            frame_rgb = cv2.cvtColor(frame, cv2.COLOR_BGR2RGB)
            pil_image = Image.fromarray(frame_rgb)

            frames_with_timestamps.append((timestamp, pil_image))
            extracted_count += 1

            if extracted_count % 10 == 0:
                print(f"  Extracted {extracted_count} frames...")

        frame_count += 1

    cap.release()
    print(f"✅ Extracted {len(frames_with_timestamps)} frames at {target_fps}fps")

    return frames_with_timestamps


def describe_frame(image: Image.Image, prompt: str = None) -> str:
    """Generate description for a single frame using BLIP-2."""
    if prompt is None:
        prompt = "Question: What is shown in this real estate property image? Answer:"

    inputs = blip_processor(image, text=prompt, return_tensors="pt")
    if torch.cuda.is_available():
        inputs = {k: v.to(device) if hasattr(v, "to") else v for k, v in inputs.items()}

    with torch.no_grad():
        generated_ids = blip_model.generate(
            **inputs, max_length=50, num_beams=3, temperature=0.7, top_p=0.9
        )

    description = blip_processor.batch_decode(generated_ids, skip_special_tokens=True)[
        0
    ]
    return description.strip()


def analyze_video_with_blip2(
    video_path: str, target_fps: float = 3.0
) -> Dict[str, Any]:
    """Analyze video frames using BLIP-2 and return timestamped descriptions."""
    print(f"🔍 Analyzing video with BLIP-2 at {target_fps}fps")

    # Extract frames
    frames_with_timestamps = extract_frames_at_fps(video_path, target_fps)

    # Analyze each frame
    timestamped_descriptions = []

    print(f"🧠 Generating descriptions for {len(frames_with_timestamps)} frames...")

    for i, (timestamp, image) in enumerate(frames_with_timestamps):
        try:
            # Generate description
            description = describe_frame(image)

            # Also get room type if possible
            room_prompt = "Question: What room or area of the property is this? Answer:"
            room_type = describe_frame(image, room_prompt)

            # Get property features
            feature_prompt = (
                "Question: What notable features or amenities are visible? Answer:"
            )
            features = describe_frame(image, feature_prompt)

            frame_data = {
                "timestamp": round(timestamp, 2),
                "frame_index": i,
                "description": description,
                "room_type": room_type,
                "features": features,
            }

            timestamped_descriptions.append(frame_data)

            # Progress update
            if (i + 1) % 5 == 0:
                print(f"  Processed {i + 1}/{len(frames_with_timestamps)} frames")
                print(f"    Latest: {timestamp:.1f}s - {description[:50]}...")

        except Exception as e:
            print(f"⚠️ Error processing frame at {timestamp:.1f}s: {str(e)}")
            continue

    print(f"✅ Generated {len(timestamped_descriptions)} frame descriptions")

    # Generate summary statistics
    room_types = {}
    all_features = []

    for desc in timestamped_descriptions:
        room = desc["room_type"].lower()
        if room not in room_types:
            room_types[room] = []
        room_types[room].append(desc["timestamp"])

        # Extract features
        if desc["features"]:
            all_features.append(desc["features"])

    return {
        "frame_descriptions": timestamped_descriptions,
        "analysis_metadata": {
            "total_frames": len(timestamped_descriptions),
            "fps_analyzed": target_fps,
            "room_types_detected": list(room_types.keys()),
            "unique_features": list(set(all_features[:20])),  # Top 20 unique features
        },
    }


def upload_json_to_s3(data: Dict, job_id: str, filename: str) -> str:
    """Upload JSON data to S3."""
    bucket = os.environ.get("S3_BUCKET_RESULTS", "unpin-real-estate-results")
    key = f"analysis/{job_id}/{filename}"

    print(f"📤 Uploading JSON to s3://{bucket}/{key}")

    json_bytes = json.dumps(data, indent=2).encode("utf-8")
    s3_client.put_object(
        Bucket=bucket, Key=key, Body=json_bytes, ContentType="application/json"
    )

    return f"s3://{bucket}/{key}"


def process_video(
    video_url: str, job_id: str, target_fps: float = 3.0
) -> Dict[str, Any]:
    """Process a single video with BLIP-2 analysis."""
    temp_dir = Path("/tmp") / job_id
    temp_dir.mkdir(exist_ok=True)

    try:
        # Download video
        local_video = str(temp_dir / "input_video.mp4")
        download_video_from_s3(video_url, local_video)

        # Analyze with BLIP-2
        analysis_result = analyze_video_with_blip2(local_video, target_fps)

        # Upload analysis results to S3
        analysis_url = upload_json_to_s3(
            analysis_result, job_id, "frame_descriptions.json"
        )

        # Create a summary for the response
        summary = {
            "total_frames_analyzed": analysis_result["analysis_metadata"][
                "total_frames"
            ],
            "fps_analyzed": target_fps,
            "rooms_detected": analysis_result["analysis_metadata"][
                "room_types_detected"
            ],
            "sample_descriptions": [
                {"timestamp": d["timestamp"], "description": d["description"]}
                for d in analysis_result["frame_descriptions"][:5]  # First 5 samples
            ],
        }

        return {
            "status": "completed",
            "video_url": video_url,
            "analysis_url": analysis_url,
            "summary": summary,
            "frame_descriptions": analysis_result[
                "frame_descriptions"
            ],  # Include all descriptions
            "analysis_metadata": analysis_result["analysis_metadata"],
        }

    finally:
        # Clean up temp files
        import shutil

        if temp_dir.exists():
            shutil.rmtree(temp_dir)


def handler(job: Dict[str, Any]) -> Dict[str, Any]:
    """Main RunPod handler function."""
    try:
        print(f"🚀 Starting BLIP-2 video analysis job: {job.get('id', 'unknown')}")
        start_time = time.time()

        # Load model if not already loaded
        if blip_model is None:
            load_blip2_model()

        # Extract input
        job_input = job.get("input", {})
        video_urls = job_input.get("video_urls", [])
        job_id = job_input.get("job_id", job.get("id", "unknown"))
        target_fps = job_input.get("target_fps", 3.0)

        if not video_urls:
            raise ValueError("No video URLs provided")

        print(f"📋 Processing {len(video_urls)} videos at {target_fps}fps")

        # Process first video (can extend to multiple)
        result = process_video(video_urls[0], job_id, target_fps)

        # Add processing time
        result["processing_time"] = time.time() - start_time
        result["job_id"] = job_id

        print(f"✅ Job completed in {result['processing_time']:.1f}s")
        return result

    except Exception as e:
        error_msg = f"Error in BLIP-2 analysis: {str(e)}\n{traceback.format_exc()}"
        print(f"❌ {error_msg}")
        return {
            "status": "failed",
            "error": error_msg,
            "job_id": job.get("input", {}).get("job_id", "unknown"),
        }


# RunPod serverless handler
runpod.serverless.start({"handler": handler})
