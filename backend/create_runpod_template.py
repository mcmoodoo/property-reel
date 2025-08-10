#!/usr/bin/env python3
"""Create a RunPod template for the video processing pipeline."""

import json
import os
import sys
import requests
from utils.config import settings


def create_template():
    """Create a RunPod template."""
    api_key = os.getenv("RUNPOD_API_KEY") or settings.runpod_api_key
    if not api_key:
        print("❌ RUNPOD_API_KEY not found")
        return None

    headers = {"Authorization": f"Bearer {api_key}", "Content-Type": "application/json"}

    # Template configuration for video processing
    template_config = {
        "name": "Real Estate Video Processor",
        "imageName": "pytorch/pytorch:2.1.0-cuda12.1-cudnn8-devel",
        "containerDiskInGb": 25,
        "volumeInGb": 0,
        "volumeMountPath": "/runpod-volume",
        "ports": ["8000/http"],
        "env": {
            "PYTHON_VERSION": "3.11",
            "AWS_REGION": settings.aws_region or "us-east-1",
            "S3_BUCKET_VIDEOS": settings.s3_bucket_videos or "",
            "S3_BUCKET_RESULTS": settings.s3_bucket_results or "",
        },
        "isPublic": False,
    }

    try:
        print("🚀 Creating RunPod template...")
        response = requests.post(
            "https://rest.runpod.io/v1/templates",
            headers=headers,
            json=template_config,
            timeout=30,
        )

        print(f"Status: {response.status_code}")
        result = response.json()

        if response.status_code == 200 or response.status_code == 201:
            template_id = result.get("id")
            print(f"✅ Template created successfully!")
            print(f"Template ID: {template_id}")
            print(f"Template Name: {result.get('name')}")
            return template_id
        else:
            print("❌ Failed to create template:")
            print(json.dumps(result, indent=2))
            return None

    except Exception as e:
        print(f"❌ Error creating template: {e}")
        return None


def create_endpoint_with_template(template_id):
    """Create endpoint using the template."""
    api_key = os.getenv("RUNPOD_API_KEY") or settings.runpod_api_key

    headers = {"Authorization": f"Bearer {api_key}", "Content-Type": "application/json"}

    endpoint_config = {
        "name": "real-estate-video-processor",
        "templateId": template_id,
        "gpuTypeIds": ["NVIDIA GeForce RTX 4090"],
        "gpuCount": 1,
        "workersMin": 0,
        "workersMax": 1,
        "scalerType": "QUEUE_DELAY",
        "scalerValue": 4,
        "idleTimeout": 5,
        "executionTimeoutMs": 900000,
    }

    try:
        print("🚀 Creating RunPod endpoint...")
        response = requests.post(
            "https://rest.runpod.io/v1/endpoints",
            headers=headers,
            json=endpoint_config,
            timeout=30,
        )

        result = response.json()

        if response.status_code == 200 or response.status_code == 201:
            endpoint_id = result.get("id")
            print(f"✅ Endpoint created successfully!")
            print(f"Endpoint ID: {endpoint_id}")
            print(f"Endpoint Name: {result.get('name')}")
            print(f"\n📝 Add this to your .env file:")
            print(f"RUNPOD_ENDPOINT_ID={endpoint_id}")
            return endpoint_id
        else:
            print("❌ Failed to create endpoint:")
            print(json.dumps(result, indent=2))
            return None

    except Exception as e:
        print(f"❌ Error creating endpoint: {e}")
        return None


def main():
    """Main function."""
    print("🔧 RunPod Template & Endpoint Creation")
    print("=" * 50)

    # Step 1: Create template
    template_id = create_template()
    if not template_id:
        print("❌ Template creation failed")
        sys.exit(1)

    # Step 2: Create endpoint
    endpoint_id = create_endpoint_with_template(template_id)
    if not endpoint_id:
        print("❌ Endpoint creation failed")
        sys.exit(1)

    print("\n🎉 Setup complete!")
    print("Next steps:")
    print("1. Add the RUNPOD_ENDPOINT_ID to your .env file")
    print("2. Test with: just test-runpod")


if __name__ == "__main__":
    main()
