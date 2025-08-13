#!/usr/bin/env python3
"""Test RunPod directly without using our API."""

import json
import os
import time
import requests

# RunPod credentials 
RUNPOD_API_KEY = os.environ.get("RUNPOD_API_KEY")
RUNPOD_ENDPOINT_ID = "54dgnxq2kd1jem"  # From .env

# S3 video that already exists
TEST_VIDEO_S3 = "s3://unpin-real-estate-videos/fresh-test-001/test.mp4"


def submit_job_to_runpod():
    """Submit job directly to RunPod."""
    if not RUNPOD_API_KEY or not RUNPOD_ENDPOINT_ID:
        print("❌ Set RUNPOD_API_KEY and RUNPOD_ENDPOINT_ID environment variables")
        return None
    
    print("\n🚀 Submitting job to RunPod...")
    print(f"  Endpoint: {RUNPOD_ENDPOINT_ID}")
    print(f"  Video: {TEST_VIDEO_S3}")
    
    # Prepare payload
    payload = {
        "input": {
            "video_urls": [TEST_VIDEO_S3],
            "property_data": {
                "property_id": "direct-test-001",
                "property_type": "residential",
            },
            "job_id": f"direct-test-{int(time.time())}",
        }
    }
    
    # Submit to RunPod
    headers = {
        "Authorization": f"Bearer {RUNPOD_API_KEY}",
        "Content-Type": "application/json",
    }
    
    url = f"https://api.runpod.ai/v2/{RUNPOD_ENDPOINT_ID}/run"
    
    try:
        response = requests.post(url, json=payload, headers=headers, timeout=30)
        
        print(f"  Response status: {response.status_code}")
        
        if response.status_code == 200:
            data = response.json()
            job_id = data.get("id")
            print(f"  ✅ Job submitted: {job_id}")
            return job_id
        else:
            print(f"  ❌ Failed: {response.text}")
            return None
            
    except Exception as e:
        print(f"  ❌ Error: {e}")
        return None


def check_status(job_id):
    """Check job status on RunPod."""
    print(f"\n⏳ Checking status for {job_id}...")
    
    headers = {
        "Authorization": f"Bearer {RUNPOD_API_KEY}",
        "Content-Type": "application/json",
    }
    
    url = f"https://api.runpod.ai/v2/{RUNPOD_ENDPOINT_ID}/status/{job_id}"
    
    for attempt in range(120):  # 10 minutes max
        try:
            response = requests.get(url, headers=headers, timeout=10)
            
            if response.status_code == 200:
                data = response.json()
                status = data.get("status")
                
                print(f"  Status: {status} (attempt {attempt + 1}/120)")
                
                if status == "COMPLETED":
                    print("  ✅ Job completed!")
                    output = data.get("output", {})
                    if output:
                        # Print summary of BLIP-2 analysis
                        print(f"  Analysis URL: {output.get('analysis_url', 'N/A')}")
                        print(f"  Total frames analyzed: {output.get('analysis_metadata', {}).get('total_frames', 0)}")
                        
                        # Show sample frame descriptions
                        descriptions = output.get('frame_descriptions', [])[:3]
                        if descriptions:
                            print("  Sample descriptions:")
                            for desc in descriptions:
                                print(f"    {desc['timestamp']}s: {desc['description']}")
                    return True
                    
                elif status == "FAILED":
                    print("  ❌ Job failed!")
                    error = data.get("error")
                    if error:
                        print(f"  Error: {error}")
                    return False
                    
            else:
                print(f"  ⚠️ Failed to get status: {response.status_code}")
                
        except Exception as e:
            print(f"  ⚠️ Error checking status: {e}")
        
        time.sleep(5)
    
    print("  ⏱️ Timeout after 10 minutes")
    return False


def main():
    """Run direct RunPod test."""
    print("\n" + "=" * 50)
    print("DIRECT RUNPOD TEST")
    print("=" * 50)
    
    # Submit job
    job_id = submit_job_to_runpod()
    if not job_id:
        print("\n❌ Failed to submit job")
        return
    
    # Check status
    success = check_status(job_id)
    
    if success:
        print("\n✅ TEST PASSED")
    else:
        print("\n❌ TEST FAILED")


if __name__ == "__main__":
    main()