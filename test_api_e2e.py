#!/usr/bin/env python3
"""End-to-end test using the FastAPI backend."""

import json
import os
import subprocess
import time
from pathlib import Path

import requests

# Configuration
API_BASE_URL = os.environ.get("API_BASE_URL", "http://localhost:8000")
RUNPOD_API_KEY = os.environ.get("RUNPOD_API_KEY")
RUNPOD_ENDPOINT_ID = os.environ.get("RUNPOD_ENDPOINT_ID")


def get_specific_video():
    videos_dir = Path("videos")
    video_path = videos_dir / "cut1.mp4"
    if video_path.exists():
        return [str(video_path)]
    return create_fallback_videos()


def get_real_videos(count=3):
    """Use real videos from videos/ folder."""
    print("🎬 Using real videos from videos/ folder...")

    videos_dir = Path("videos")
    if not videos_dir.exists():
        print("  ❌ videos/ folder not found")
        print("  Creating test videos instead...")
        return create_fallback_videos()

    # Get available video files
    all_video_files = list(videos_dir.glob("*.MP4")) + list(videos_dir.glob("*.mp4"))

    if not all_video_files:
        print("  ❌ No video files found in videos/ folder")
        return create_fallback_videos()

    # Exclude specific videos
    excluded_videos = {"C0058.mp4", "C0058.MP4", "C0063.mp4", "C0063.MP4"}
    video_files = [v for v in all_video_files if v.name not in excluded_videos]

    if excluded_videos & {v.name for v in all_video_files}:
        excluded_found = excluded_videos & {v.name for v in all_video_files}
        print(f"  🚫 Excluding videos: {', '.join(excluded_found)}")

    if not video_files:
        print("  ❌ No usable video files found after exclusions")
        return create_fallback_videos()

    # Use first N videos
    selected_videos = video_files[:count]
    print(f"  Using {len(selected_videos)} videos:")

    video_paths = []
    for video in selected_videos:
        # Get video info
        cmd = [
            "ffprobe",
            "-v",
            "error",
            "-show_entries",
            "format=duration,size",
            "-of",
            "json",
            str(video),
        ]
        result = subprocess.run(cmd, capture_output=True, text=True)

        if result.returncode == 0:
            info = json.loads(result.stdout)
            duration = float(info["format"].get("duration", 0))
            size_mb = int(info["format"].get("size", 0)) / (1024 * 1024)
            print(f"    • {video.name} ({duration:.1f}s, {size_mb:.1f}MB)")
        else:
            print(f"    • {video.name}")

        video_paths.append(str(video))

    return video_paths


def create_fallback_videos():
    """Create test videos if real videos aren't available."""
    print("  Creating fallback test videos...")

    test_videos = []
    for i, duration in enumerate([15, 20, 10], 1):
        filename = f"test_video_{i}.mp4"
        if not Path(filename).exists():
            cmd = [
                "ffmpeg",
                "-f",
                "lavfi",
                "-i",
                f"testsrc=duration={duration}:size=640x480:rate=30",
                "-c:v",
                "libx264",
                "-pix_fmt",
                "yuv420p",
                filename,
            ]
            subprocess.run(cmd, capture_output=True)
            print(f"    ✅ Created {filename} ({duration}s)")
        test_videos.append(filename)

    return test_videos


def test_health_check():
    """Test API health endpoint."""
    print("\n🏥 Testing API health...")

    response = requests.get(f"{API_BASE_URL}/health/", timeout=30)
    if response.status_code == 200:
        print(f"  ✅ API is healthy: {response.json()}")
        return True
    else:
        print(f"  ❌ API health check failed: {response.status_code}")
        return False


def test_detailed_health():
    """Test detailed health with all services."""
    print("\n🔍 Testing detailed health...")

    response = requests.get(f"{API_BASE_URL}/health/detailed", timeout=60)
    if response.status_code == 200:
        health_data = response.json()
        components = health_data.get("components", {})

        # Check database
        db_status = components.get("database", {}).get("status", "unknown")
        print(f"  Database: {'✅' if db_status == 'healthy' else '❌'} ({db_status})")

        # Check S3
        s3_status = components.get("s3", {}).get("status", "unknown")
        print(f"  S3: {'✅' if s3_status == 'healthy' else '❌'} ({s3_status})")

        # Check RunPod
        runpod_status = components.get("runpod", {}).get("status", "unknown")
        print(
            f"  RunPod: {'✅' if runpod_status == 'healthy' else '❌'} ({runpod_status})"
        )

        # Return simplified structure for compatibility
        return {
            "database": {"connected": db_status == "healthy"},
            "s3": {"configured": s3_status == "healthy"},
            "runpod": {"configured": runpod_status == "healthy"},
            "raw": health_data,
        }
    else:
        print(f"  ❌ Detailed health check failed: {response.status_code}")
        return None


def create_job(video_files):
    """Create a processing job via API."""
    print("\n📝 Creating job via API...")

    # Show total upload size
    total_size = 0
    file_sizes = {}
    for video in video_files:
        size = Path(video).stat().st_size
        file_sizes[video] = size
        total_size += size
        print(f"  📁 {Path(video).name}: {size / (1024 * 1024):.1f}MB")

    print(f"  📊 Total upload size: {total_size / (1024 * 1024):.1f}MB")

    if total_size > 100 * 1024 * 1024:  # > 100MB
        print("  ⏳ Large upload detected - this may take several minutes...")

    # Prepare multipart form data with files
    print("  🔄 Preparing upload files...")
    files = []
    for i, video in enumerate(video_files, 1):
        print(f"    • Opening file {i}/{len(video_files)}: {Path(video).name}")
        files.append(("files", (Path(video).name, open(video, "rb"), "video/mp4")))

    # Property data must be a JSON string
    property_data = {
        "property_id": "test-property-001",
        "property_address": "123 Test Street, Test City",
        "property_type": "residential",  # Valid value from the allowed list
    }

    data = {"property_data": json.dumps(property_data)}

    print("  🚀 Starting upload to API server...")
    upload_start = time.time()

    try:
        # Set a longer timeout for large uploads
        # At least 5 minutes, +1s per MB
        timeout = max(300, total_size / (1024 * 1024))
        print(f"  ⏱️ Upload timeout set to {int(timeout)} seconds")

        response = requests.post(
            f"{API_BASE_URL}/api/v1/jobs/", files=files, data=data, timeout=timeout
        )

        upload_time = time.time() - upload_start
        upload_speed = total_size / upload_time / (1024 * 1024)  # MB/s
        print(f"  ⏱️ Upload completed in {upload_time:.1f}s ({upload_speed:.1f}MB/s)")

        # Close file handles
        for _, file_tuple in files:
            file_tuple[1].close()

        if response.status_code == 201:
            job_data = response.json()
            print(f"  ✅ Job created: {job_data['job_id']}")
            print(f"  Status: {job_data['status']}")
            print(f"  Videos: {job_data['video_count']}")
            return job_data["job_id"]
        else:
            print(f"  ❌ Failed to create job: {response.status_code}")
            print(f"  Response: {response.text}")
            return None

    except requests.exceptions.Timeout:
        print(f"  ❌ Upload timed out after {timeout} seconds")
        print("  💡 Try reducing video file sizes or check your internet connection")
        return None
    except Exception as e:
        print(f"  ❌ Error creating job: {e}")
        return None
    finally:
        # Ensure all files are closed
        for _, file_tuple in files:
            try:
                file_tuple[1].close()
            except:
                pass


def check_job_status(job_id):
    """Check job status via API and poll RunPod directly."""
    print(f"\n⏳ Monitoring job {job_id}...")

    # First, get the RunPod job ID from our API
    response = requests.get(f"{API_BASE_URL}/api/v1/jobs/{job_id}")
    if response.status_code != 200:
        print(f"  ❌ Failed to get job info: {response.status_code}")
        return None

    job_data = response.json()
    runpod_job_id = job_data.get("runpod_job_id")

    if not runpod_job_id:
        print("  ⚠️ Job not yet submitted to RunPod, waiting...")
        time.sleep(5)
        return check_job_status(job_id)  # Retry

    print(f"  RunPod Job ID: {runpod_job_id}")

    # Now poll RunPod directly since webhooks won't work locally
    RUNPOD_API_KEY = os.environ.get("RUNPOD_API_KEY")
    RUNPOD_ENDPOINT_ID = os.environ.get("RUNPOD_ENDPOINT_ID")

    if not RUNPOD_API_KEY or not RUNPOD_ENDPOINT_ID:
        print("  ⚠️ Set RUNPOD_API_KEY and RUNPOD_ENDPOINT_ID to poll RunPod directly")
        print("  Falling back to API polling only...")
        return poll_api_only(job_id)

    headers = {
        "Authorization": f"Bearer {RUNPOD_API_KEY}",
        "Content-Type": "application/json",
    }

    max_attempts = 60  # 5 minutes
    for attempt in range(max_attempts):
        # Check RunPod status directly
        runpod_response = requests.get(
            f"https://rest.runpod.io/v1/endpoints/{RUNPOD_ENDPOINT_ID}/requests/{runpod_job_id}",
            headers=headers,
        )

        if runpod_response.status_code == 200:
            runpod_data = runpod_response.json()
            runpod_status = runpod_data.get("status")

            print(
                f"  RunPod Status: {runpod_status} (attempt {attempt + 1}/{max_attempts})"
            )

            if runpod_status == "COMPLETED":
                print("\n✅ RunPod job completed successfully!")
                output = runpod_data.get("output", {})
                print(f"  Result URL: {output.get('result_url')}")
                print(
                    f"  Processing time: {runpod_data.get('executionTime', 0) / 1000:.1f}s"
                )

                # Since webhook won't fire, manually update our API
                print("  📝 Manually updating job status in API...")
                update_job_manually(job_id, runpod_data)

                # Get updated job data from our API
                response = requests.get(f"{API_BASE_URL}/api/v1/jobs/{job_id}")
                if response.status_code == 200:
                    return response.json()
                return {"status": "completed", "result_url": output.get("result_url")}

            elif runpod_status == "FAILED":
                print("\n❌ RunPod job failed!")
                print(f"  Error: {runpod_data.get('error')}")
                return {"status": "failed", "error": runpod_data.get("error")}

            time.sleep(5)
        else:
            print(f"  ⚠️ Failed to get RunPod status: {runpod_response.status_code}")
            time.sleep(5)

    print("\n⏱️ Timeout waiting for job completion")
    return None


def poll_api_only(job_id):
    """Fallback to only polling our API (won't update without webhook)."""
    max_attempts = 60
    for attempt in range(max_attempts):
        response = requests.get(f"{API_BASE_URL}/api/v1/jobs/{job_id}")
        if response.status_code == 200:
            job_data = response.json()
            status = job_data["status"]
            print(f"  API Status: {status} (attempt {attempt + 1}/{max_attempts})")

            if status in ["completed", "failed"]:
                return job_data

            time.sleep(5)
    return None


def update_job_manually(job_id, runpod_data):
    """Manually update job status in our API (simulating webhook)."""
    # Simulate the webhook payload
    webhook_payload = {
        "job_id": job_id,
        "status": runpod_data.get("status"),
        "output": runpod_data.get("output", {}),
        "error": runpod_data.get("error"),
    }

    # Call our webhook endpoint manually
    response = requests.post(f"{API_BASE_URL}/webhook/runpod", json=webhook_payload)

    if response.status_code == 200:
        print("  ✅ Job status updated in API")
    else:
        print(f"  ⚠️ Failed to update job status: {response.status_code}")


def download_result(job_data):
    """Download the final result video."""
    print("\n📥 Downloading result...")

    result_url = job_data.get("result_url")
    if not result_url:
        print("  ❌ No result URL in job data")
        return False

    # If it's an S3 URL, download using AWS CLI
    if result_url.startswith("s3://"):
        local_file = f"result_{job_data['job_id']}.mp4"
        cmd = ["aws", "s3", "cp", result_url, local_file]
        result = subprocess.run(cmd, capture_output=True)

        if result.returncode == 0:
            print(f"  ✅ Downloaded result to: {local_file}")

            # Get video info
            cmd = [
                "ffprobe",
                "-v",
                "error",
                "-show_entries",
                "format=duration",
                "-of",
                "json",
                local_file,
            ]
            result = subprocess.run(cmd, capture_output=True, text=True)

            if result.returncode == 0:
                info = json.loads(result.stdout)
                duration = float(info["format"]["duration"])
                print(f"  📊 Final video duration: {duration:.1f} seconds")

            return True
        else:
            print("  ❌ Failed to download result")
            return False
    else:
        print(f"  ℹ️ Result URL: {result_url}")
        return True


def test_webhook_endpoint():
    """Test webhook endpoint availability."""
    print("\n🔔 Testing webhook endpoint...")

    # Send a test webhook
    test_payload = {
        "job_id": "test-webhook",
        "status": "COMPLETED",
        "output": {"test": True},
    }

    response = requests.post(f"{API_BASE_URL}/webhook/runpod", json=test_payload)

    if response.status_code == 200:
        print("  ✅ Webhook endpoint is working")
        return True
    else:
        print(f"  ⚠️ Webhook returned: {response.status_code}")
        return False


def cleanup(video_files):
    """Clean up test files (only removes generated test videos, not real ones)."""
    print("\n🧹 Cleaning up...")
    for video in video_files:
        # Only clean up test videos, not real ones from videos/ folder
        if "test_video_" in video and Path(video).exists():
            Path(video).unlink()
            print(f"  Removed {video}")
        elif Path(video).name.startswith("test_video_"):
            # Just in case path structure is different
            if Path(video).exists():
                Path(video).unlink()
                print(f"  Removed {video}")


def main():
    """Run full API end-to-end test."""
    print("=" * 50)
    print("🧪 FASTAPI BACKEND END-TO-END TEST")
    print("=" * 50)
    print(f"📍 API URL: {API_BASE_URL}")

    if RUNPOD_API_KEY and RUNPOD_ENDPOINT_ID:
        print("✅ RunPod credentials configured for direct polling")
    else:
        print("⚠️ Set RUNPOD_API_KEY and RUNPOD_ENDPOINT_ID for direct RunPod polling")
        print(
            "   Without these, the test will only poll your API (which won't update without webhooks)"
        )

    # Step 1: Check API health
    if not test_health_check():
        print("\n❌ API is not running. Start it with: just dev")
        return

    # Step 2: Check detailed health
    health = test_detailed_health()
    if not health:
        return

    if not health["database"]["connected"]:
        print("\n❌ Database not connected. Start it with: just db-start")
        return

    if not health["runpod"]["configured"]:
        print("\n⚠️ RunPod not configured. Jobs will fail.")

    # Step 3: Test webhook endpoint (optional, will work but won't receive real webhooks)
    # test_webhook_endpoint()  # Commented out since we're polling directly

    # Step 4: Get specific video
    video_files = get_specific_video()

    # Step 5: Create job via API
    print("\n" + "=" * 30)
    print("📤 STEP 5: UPLOADING VIDEOS")
    print("=" * 30)

    job_id = create_job(video_files)
    if not job_id:
        print("\n❌ Failed to create job")
        cleanup(video_files)
        return

    print(f"\n✅ Job creation completed! Job ID: {job_id}")

    # Step 6: Monitor job status
    final_job = check_job_status(job_id)

    if final_job and final_job["status"] == "completed":
        # Step 7: Download result
        download_result(final_job)

        print("\n" + "=" * 50)
        print("✅ API END-TO-END TEST PASSED!")
        print("=" * 50)
    else:
        print("\n" + "=" * 50)
        print("❌ API END-TO-END TEST FAILED!")
        print("=" * 50)

    # Cleanup
    print("\nClean up test videos? (y/n): ", end="")
    if input().lower() == "y":
        cleanup(video_files)


if __name__ == "__main__":
    main()
