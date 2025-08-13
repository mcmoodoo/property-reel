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


def create_job(video_file):
    """Create a processing job."""
    print("\n📝 Creating job...")

    # Get file size
    size_mb = Path(video_file).stat().st_size / (1024 * 1024)
    print(f"  Uploading: {Path(video_file).name} ({size_mb:.1f}MB)")

    # Prepare files and data
    files = [("files", (Path(video_file).name, open(video_file, "rb"), "video/mp4"))]
    property_data = {
        "property_id": "test-001",
        "property_type": "residential",
    }
    data = {"property_data": json.dumps(property_data)}

    # Upload
    try:
        response = requests.post(
            f"{API_BASE_URL}/api/v1/jobs/", files=files, data=data, timeout=300
        )

        # Close file
        files[0][1][1].close()

        if response.status_code == 201:
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

    # Get job info
    response = requests.get(f"{API_BASE_URL}/api/v1/jobs/{job_id}")
    if response.status_code != 200:
        print("  ❌ Failed to get job info")
        return None

    job_data = response.json()
    runpod_job_id = job_data.get("runpod_job_id")

    if not runpod_job_id:
        print("  ⚠️ No RunPod job ID yet")
        return None

    print(f"  RunPod ID: {runpod_job_id}")

    # Poll RunPod directly if credentials available
    if RUNPOD_API_KEY and RUNPOD_ENDPOINT_ID:
        return poll_runpod(job_id, runpod_job_id)
    else:
        print("  ⚠️ No RunPod credentials, can't poll status")
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

    # Find video file
    video_file = "videos/C0049.MP4"
    if not Path(video_file).exists():
        print(f"❌ Video file not found: {video_file}")
        return

    # Create job
    job_id = create_job(video_file)
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
