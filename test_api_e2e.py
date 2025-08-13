#!/usr/bin/env python3
"""Simple end-to-end test for the API."""

import json
import os
import time
from pathlib import Path

import requests

# Configuration
API_BASE_URL = os.environ.get("API_BASE_URL", "http://localhost:8000")
RUNPOD_API_KEY = os.environ.get("RUNPOD_API_KEY")
RUNPOD_ENDPOINT_ID = os.environ.get("RUNPOD_ENDPOINT_ID")


def test_health():
    """Test API health."""
    print("\n🏥 Testing API health...")
    response = requests.get(f"{API_BASE_URL}/health/", timeout=30)
    if response.status_code == 200:
        print("  ✅ API is healthy")
        return True
    print(f"  ❌ API health check failed: {response.status_code}")
    return False


def test_detailed_health():
    """Test detailed health."""
    print("\n🔍 Testing detailed health...")
    response = requests.get(f"{API_BASE_URL}/health/detailed", timeout=60)
    if response.status_code != 200:
        print(f"  ❌ Detailed health check failed: {response.status_code}")
        return None

    health_data = response.json()
    components = health_data.get("components", {})

    db_status = components.get("database", {}).get("status", "unknown")
    s3_status = components.get("s3", {}).get("status", "unknown")
    runpod_status = components.get("runpod", {}).get("status", "unknown")

    print(f"  Database: {'✅' if db_status == 'healthy' else '❌'}")
    print(f"  S3: {'✅' if s3_status == 'healthy' else '❌'}")
    print(f"  RunPod: {'✅' if runpod_status == 'healthy' else '❌'}")

    return {
        "database": db_status == "healthy",
        "s3": s3_status == "healthy",
        "runpod": runpod_status == "healthy",
    }


def create_job():
    """Create a processing job (no actual upload needed)."""
    print("\n📝 Creating job...")
    print("  Note: Using hardcoded test video, no upload required")
    
    # Create a dummy file for the API
    import tempfile
    with tempfile.NamedTemporaryFile(suffix=".mp4") as dummy_file:
        dummy_file.write(b"dummy video content")
        dummy_file.seek(0)
        
        files = [("files", ("test.mp4", dummy_file, "video/mp4"))]
        property_data = {
            "property_id": "test-001",
            "property_type": "residential",
        }
        data = {"property_data": json.dumps(property_data)}
        
        try:
            response = requests.post(
                f"{API_BASE_URL}/api/v1/jobs/",
                files=files,
                data=data,
                timeout=30  # Much shorter timeout since no real upload
            )
            
            if response.status_code == 200:
                job_data = response.json()
                job_id = job_data["job_id"]
                print(f"  ✅ Job created: {job_id}")
                return job_id
            else:
                print(f"  ❌ Failed: {response.status_code}")
                print(f"  Error: {response.text}")
                return None
        except Exception as e:
            print(f"  ❌ Error: {e}")
            return None


def check_job_status(job_id):
    """Check job status."""
    print(f"\n⏳ Checking job {job_id}...")

    # Wait a moment for RunPod submission
    time.sleep(2)
    
    # Get job info
    response = requests.get(f"{API_BASE_URL}/api/v1/jobs/{job_id}")
    if response.status_code != 200:
        print("  ❌ Failed to get job info")
        return None

    job_data = response.json()
    status = job_data.get("status")
    
    print(f"  Job status: {status}")
    
    # If already completed, we're done
    if status == "completed":
        print("  ✅ Job completed!")
        return job_data
    elif status == "failed":
        print("  ❌ Job failed!")
        return job_data
    
    # Otherwise poll for completion
    return poll_api_only(job_id)


def poll_runpod(job_id, runpod_job_id):
    """Poll RunPod directly."""
    headers = {
        "Authorization": f"Bearer {RUNPOD_API_KEY}",
        "Content-Type": "application/json",
    }

    for attempt in range(60):  # 5 minutes max
        url = f"https://api.runpod.ai/v2/{RUNPOD_ENDPOINT_ID}/status/{runpod_job_id}"
        response = requests.get(url, headers=headers)

        if response.status_code == 200:
            data = response.json()
            status = data.get("status")
            print(f"  Status: {status} (attempt {attempt + 1}/60)")

            if status == "COMPLETED":
                print("  ✅ Job completed!")
                return {"status": "completed"}
            elif status == "FAILED":
                print("  ❌ Job failed!")
                return {"status": "failed"}
        else:
            print(f"  ⚠️ Failed to get status: {response.status_code}")

        time.sleep(5)

    print("  ⏱️ Timeout")
    return None


def poll_api_only(job_id):
    """Poll our API only."""
    for attempt in range(60):
        response = requests.get(f"{API_BASE_URL}/api/v1/jobs/{job_id}")
        if response.status_code == 200:
            job_data = response.json()
            status = job_data["status"]
            print(f"  API Status: {status} (attempt {attempt + 1}/60)")

            if status in ["completed", "failed"]:
                return job_data

        time.sleep(5)

    return None


def main():
    """Run the test."""
    print("\n" + "=" * 50)
    print("E2E TEST")
    print("=" * 50)

    # Check health
    if not test_health():
        print("❌ API not running")
        return

    # Check services
    health = test_detailed_health()
    if not health:
        return

    if not health["database"]:
        print("❌ Database not connected")
        return

    # Create job (no video file needed)
    job_id = create_job()
    if not job_id:
        print("❌ Failed to create job")
        return

    # Check status
    result = check_job_status(job_id)

    if result and result["status"] == "completed":
        print("\n✅ TEST PASSED")
    else:
        print("\n❌ TEST FAILED")


if __name__ == "__main__":
    main()
