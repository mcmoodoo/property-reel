#!/usr/bin/env python3
"""Fresh RunPod setup from scratch."""

import json
import os
import time

import requests

# Configuration
RUNPOD_API_KEY = os.environ.get("RUNPOD_API_KEY")
if not RUNPOD_API_KEY:
    print("❌ Set RUNPOD_API_KEY environment variable")
    exit(1)

BASE_URL = "https://rest.runpod.io/v1"
HEADERS = {
    "Authorization": f"Bearer {RUNPOD_API_KEY}",
    "Content-Type": "application/json",
}

# Your public GHCR image
IMAGE_NAME = "ghcr.io/mcmoodoo/real-estate-processor:latest"


def create_template():
    """Create new RunPod template."""
    print("📦 Creating new template...")

    template_data = {
        "name": "video-processor-poc-2",
        "imageName": IMAGE_NAME,
        "dockerStartCmd": ["python", "-u", "handler.py"],
        "volumeInGb": 20,
        "containerDiskInGb": 10,
        "volumeMountPath": "/workspace",
        "env": {
            "AWS_ACCESS_KEY_ID": os.environ.get("AWS_ACCESS_KEY_ID", ""),
            "AWS_SECRET_ACCESS_KEY": os.environ.get("AWS_SECRET_ACCESS_KEY", ""),
            "AWS_REGION": "us-east-1",
            "S3_BUCKET_VIDEOS": "unpin-real-estate-videos",
            "S3_BUCKET_RESULTS": "unpin-real-estate-results",
        },
        "isPublic": False,
        "readme": "POC Video Processing Template",
    }

    response = requests.post(
        f"{BASE_URL}/templates", headers=HEADERS, json=template_data
    )

    if response.status_code in [200, 201]:
        template = response.json()
        print(f"✅ Template created: {template.get('id')}")
        return template.get("id")
    else:
        print(f"❌ Failed to create template: {response.status_code}")
        print(response.text)
        return None


def create_endpoint(template_id):
    """Create new RunPod endpoint."""
    print("🚀 Creating new endpoint...")

    endpoint_data = {
        "name": "video-processor-endpoint",
        "templateId": template_id,
        "gpuTypeIds": [
            "NVIDIA GeForce RTX 3090",
            "NVIDIA RTX A4000",
        ],  # Adjust as needed
        "workersMin": 0,
        "workersMax": 1,
        "idleTimeout": 60,  # Seconds before worker shuts down
        "scalerType": "REQUEST_COUNT",
        "scalerValue": 1,
    }

    response = requests.post(
        f"{BASE_URL}/endpoints", headers=HEADERS, json=endpoint_data
    )

    if response.status_code in [200, 201]:
        endpoint = response.json()
        print(f"✅ Endpoint created: {endpoint.get('id')}")
        return endpoint.get("id")
    else:
        print(f"❌ Failed to create endpoint: {response.status_code}")
        print(response.text)
        return None


def test_endpoint(endpoint_id):
    """Submit test job to endpoint."""
    print("🧪 Testing endpoint...")

    test_job = {
        "input": {
            "video_urls": ["s3://unpin-real-estate-videos/test.mp4"],
            "job_id": f"test-{int(time.time())}",
        }
    }

    response = requests.post(
        f"{BASE_URL}/endpoints/{endpoint_id}/run", headers=HEADERS, json=test_job
    )

    if response.status_code in [200, 201]:
        job = response.json()
        print(f"✅ Test job submitted: {job.get('id')}")
        return job.get("id")
    else:
        print(f"❌ Failed to submit test job: {response.status_code}")
        print(response.text)
        return None


def main():
    """Main setup flow."""
    print("🔧 Starting fresh RunPod setup...")
    print(f"📸 Using image: {IMAGE_NAME}")
    print("-" * 50)

    # Create template
    template_id = create_template()
    if not template_id:
        print("❌ Setup failed at template creation")
        return

    print(f"📝 Template ID: {template_id}")
    time.sleep(2)

    # Create endpoint
    endpoint_id = create_endpoint(template_id)
    if not endpoint_id:
        print("❌ Setup failed at endpoint creation")
        return

    print(f"🎯 Endpoint ID: {endpoint_id}")

    # Save configuration
    config = {
        "template_id": template_id,
        "endpoint_id": endpoint_id,
        "image": IMAGE_NAME,
        "created_at": time.strftime("%Y-%m-%d %H:%M:%S"),
    }

    with open("runpod_config.json", "w") as f:
        json.dump(config, f, indent=2)

    print("-" * 50)
    print("✅ Setup complete! Configuration saved to runpod_config.json")
    print("\n📋 Next steps:")
    print(f"1. Update .env with RUNPOD_ENDPOINT_ID={endpoint_id}")
    print("2. Update GitHub Actions secrets with new endpoint ID")
    print(f"3. Test with: just runpod-status {endpoint_id}")

    # Optional: Submit test job
    print("\n🧪 Submit test job? (y/n): ", end="")
    if input().lower() == "y":
        job_id = test_endpoint(endpoint_id)
        if job_id:
            print("📊 Check job status:")
            print("   curl -H 'Authorization: Bearer $RUNPOD_API_KEY' \\")
            print(f"        '{BASE_URL}/endpoints/{endpoint_id}/requests/{job_id}'")


if __name__ == "__main__":
    main()
