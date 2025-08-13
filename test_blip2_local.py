#!/usr/bin/env python3
"""Test BLIP-2 frame analysis locally (without RunPod)."""

import json
import cv2
from PIL import Image
from pathlib import Path


def extract_frames_at_fps(video_path: str, target_fps: float = 3.0, max_frames: int = 10):
    """Extract frames from video at specified FPS rate (limited for testing)."""
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
    frame_interval = max(1, int(video_fps / target_fps))
    
    frame_count = 0
    extracted_count = 0
    
    while extracted_count < max_frames:
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
            
            print(f"  Frame {extracted_count}: {timestamp:.2f}s")
        
        frame_count += 1
    
    cap.release()
    print(f"✅ Extracted {len(frames_with_timestamps)} frames at {target_fps}fps")
    
    return frames_with_timestamps


def test_frame_extraction():
    """Test frame extraction without BLIP-2 (for quick validation)."""
    video_path = "videos/cut1.mp4"
    
    if not Path(video_path).exists():
        print(f"❌ Video not found: {video_path}")
        print("Please ensure you have a test video at videos/cut1.mp4")
        return
    
    print(f"\n🎬 Testing frame extraction on {video_path}")
    
    # Extract frames
    frames = extract_frames_at_fps(video_path, target_fps=3.0, max_frames=10)
    
    # Create mock descriptions (without loading BLIP-2)
    mock_descriptions = []
    for timestamp, image in frames:
        mock_descriptions.append({
            "timestamp": round(timestamp, 2),
            "description": f"Frame at {timestamp:.2f}s",
            "room_type": "unknown",
            "features": "mock features",
            "image_size": image.size
        })
    
    # Save sample output
    output = {
        "video_path": video_path,
        "frame_descriptions": mock_descriptions,
        "analysis_metadata": {
            "total_frames": len(frames),
            "fps_analyzed": 3.0,
            "test_mode": True
        }
    }
    
    output_file = "test_frame_analysis.json"
    with open(output_file, "w") as f:
        json.dump(output, f, indent=2)
    
    print(f"\n✅ Test complete! Sample output saved to {output_file}")
    print(f"   Extracted {len(frames)} frames")
    print(f"   Frame timestamps: {[f['timestamp'] for f in mock_descriptions]}")


def test_with_blip2_mini():
    """Test with a smaller BLIP model for local testing."""
    try:
        from transformers import BlipProcessor, BlipForConditionalGeneration
        import torch
        
        print("\n🤖 Loading BLIP model (base version for testing)...")
        
        # Use smaller model for testing
        model_name = "Salesforce/blip-image-captioning-base"
        
        processor = BlipProcessor.from_pretrained(model_name)
        model = BlipForConditionalGeneration.from_pretrained(model_name)
        model.eval()
        
        print("✅ Model loaded")
        
        # Test on single frame
        video_path = "videos/cut1.mp4"
        if not Path(video_path).exists():
            print(f"❌ Video not found: {video_path}")
            return
        
        # Extract one frame
        frames = extract_frames_at_fps(video_path, target_fps=1.0, max_frames=1)
        
        if frames:
            timestamp, image = frames[0]
            print(f"\n🔍 Analyzing frame at {timestamp:.2f}s...")
            
            # Generate description
            inputs = processor(image, return_tensors="pt")
            
            with torch.no_grad():
                generated_ids = model.generate(**inputs, max_length=30)
            
            description = processor.batch_decode(generated_ids, skip_special_tokens=True)[0]
            
            print(f"📝 Description: {description}")
            
            return {
                "timestamp": timestamp,
                "description": description,
                "model": model_name
            }
            
    except ImportError:
        print("⚠️ Transformers library not installed")
        print("Run: pip install transformers torch")
        return None


if __name__ == "__main__":
    print("=" * 50)
    print("BLIP-2 Frame Analysis Test")
    print("=" * 50)
    
    # Test basic frame extraction
    test_frame_extraction()
    
    # Optionally test with BLIP model
    print("\n" + "=" * 50)
    print("Optional: Test with BLIP model")
    print("=" * 50)
    
    try:
        result = test_with_blip2_mini()
        if result:
            print(f"\n✨ BLIP test successful!")
            print(json.dumps(result, indent=2))
    except Exception as e:
        print(f"⚠️ BLIP test skipped: {e}")