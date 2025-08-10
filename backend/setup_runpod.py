#!/usr/bin/env python3
"""Helper script for RunPod endpoint setup and management."""

import json
import os
import sys
import requests
from utils.config import settings


def get_runpod_api_key():
    """Get RunPod API key from environment or settings."""
    api_key = os.getenv("RUNPOD_API_KEY") or settings.runpod_api_key
    if not api_key:
        print("❌ RUNPOD_API_KEY not found in environment or .env file")
        print("Please set it: export RUNPOD_API_KEY=your_key_here")
        sys.exit(1)
    return api_key


def list_templates():
    """List available RunPod templates."""
    api_key = get_runpod_api_key()

    headers = {"Authorization": f"Bearer {api_key}", "Content-Type": "application/json"}

    try:
        response = requests.get("https://rest.runpod.io/v1/templates", headers=headers)
        response.raise_for_status()

        templates = response.json()

        print("🔍 Available RunPod Templates:")
        print("-" * 50)

        for template in templates:
            print(f"Name: {template.get('name', 'N/A')}")
            print(f"ID: {template.get('id', 'N/A')}")
            print(f"Docker Image: {template.get('dockerArgs', 'N/A')}")
            print(f"Runtime: {template.get('runtime', 'N/A')}")
            print("-" * 30)

        return templates

    except requests.RequestException as e:
        print(f"❌ Failed to list templates: {e}")
        return []


def list_endpoints():
    """List existing RunPod endpoints."""
    api_key = get_runpod_api_key()

    headers = {"Authorization": f"Bearer {api_key}", "Content-Type": "application/json"}

    try:
        response = requests.get("https://rest.runpod.io/v1/endpoints", headers=headers)
        response.raise_for_status()

        endpoints = response.json()

        print("🚀 Your RunPod Endpoints:")
        print("-" * 50)

        for endpoint in endpoints:
            print(f"Name: {endpoint.get('name', 'N/A')}")
            print(f"ID: {endpoint.get('id', 'N/A')}")
            print(f"Status: {endpoint.get('status', 'N/A')}")
            print(
                f"Workers: {endpoint.get('workersMin', 0)}-{endpoint.get('workersMax', 0)}"
            )
            print(f"GPU Type: {endpoint.get('gpuTypeIds', 'N/A')}")
            print("-" * 30)

        return endpoints

    except requests.RequestException as e:
        print(f"❌ Failed to list endpoints: {e}")
        return []


def create_ml_template():
    """Create a template for the ML processing pipeline."""
    api_key = get_runpod_api_key()

    headers = {"Authorization": f"Bearer {api_key}", "Content-Type": "application/json"}

    template_config = {
        "name": "Real Estate Video Processor",
        "dockerArgs": "runpod/pytorch:2.1-py3.11-cuda12.1.1-devel-ubuntu22.04",
        "containerDiskInGb": 25,
        "volumeInGb": 0,
        "volumeMountPath": "/runpod-volume",
        "ports": "8000/http",
        "env": {
            "PYTHON_VERSION": "3.11",
            "PYTORCH_VERSION": "2.1",
            "CUDA_VERSION": "12.1",
            "AWS_ACCESS_KEY_ID": settings.aws_access_key_id or "",
            "AWS_SECRET_ACCESS_KEY": settings.aws_secret_access_key or "",
            "AWS_REGION": settings.aws_region,
            "S3_BUCKET_VIDEOS": settings.s3_bucket_videos,
            "S3_BUCKET_RESULTS": settings.s3_bucket_results,
        },
        "isPublic": False,
    }

    try:
        response = requests.post(
            "https://rest.runpod.io/v1/templates", headers=headers, json=template_config
        )
        response.raise_for_status()

        template = response.json()
        print(f"✅ Created template: {template.get('id')}")
        print(f"Template name: {template.get('name')}")

        return template.get("id")

    except requests.RequestException as e:
        print(f"❌ Failed to create template: {e}")
        return None


def create_endpoint_with_template(template_id):
    """Create an endpoint using a template."""
    api_key = get_runpod_api_key()

    headers = {"Authorization": f"Bearer {api_key}", "Content-Type": "application/json"}

    endpoint_config = {
        "name": "real-estate-video-processor",
        "templateId": template_id,
        "computeType": "GPU",
        "gpuTypeIds": ["NVIDIA GeForce RTX 4090"],  # Optimal for AI/ML workloads
        "gpuCount": 1,
        "allowedCudaVersions": ["12.1", "12.8"],  # Compatible CUDA versions
        "workersMin": 0,
        "workersMax": 3,
        "scalerType": "QUEUE_DELAY",
        "scalerValue": 4,
        "idleTimeout": 5,
        "executionTimeoutMs": 900000,  # 15 minutes for video processing
    }

    try:
        response = requests.post(
            "https://rest.runpod.io/v1/endpoints", headers=headers, json=endpoint_config
        )
        response.raise_for_status()

        endpoint = response.json()
        endpoint_id = endpoint.get("id")

        print(f"✅ Created endpoint: {endpoint_id}")
        print(f"Endpoint name: {endpoint.get('name')}")
        print(f"\n📝 Add this to your .env file:")
        print(f"RUNPOD_ENDPOINT_ID={endpoint_id}")

        return endpoint_id

    except requests.RequestException as e:
        print(f"❌ Failed to create endpoint: {e}")
        return None


def main():
    """Main setup workflow."""
    if len(sys.argv) < 2:
        print("Usage: python setup_runpod.py <command>")
        print("Commands:")
        print("  templates     - List available templates")
        print("  endpoints     - List your endpoints")
        print("  create        - Create template and endpoint")
        print("  setup         - Interactive setup")
        sys.exit(1)

    command = sys.argv[1]

    if command == "templates":
        list_templates()
    elif command == "endpoints":
        list_endpoints()
    elif command == "create":
        print("🚀 Creating RunPod template and endpoint...")
        template_id = create_ml_template()
        if template_id:
            create_endpoint_with_template(template_id)
    elif command == "setup":
        print("🔧 RunPod Interactive Setup")
        print("-" * 30)

        # Check current endpoints
        endpoints = list_endpoints()
        if endpoints:
            print(f"\n⚠️  You already have {len(endpoints)} endpoint(s).")
            choice = input("Create a new one anyway? (y/N): ").strip().lower()
            if choice != "y":
                print("Setup cancelled.")
                return

        # Create new template and endpoint
        template_id = create_ml_template()
        if template_id:
            endpoint_id = create_endpoint_with_template(template_id)
            if endpoint_id:
                print("\n🎉 Setup complete!")
                print("Next steps:")
                print("1. Build and push your ML pipeline Docker image")
                print("2. Update the template with your actual image")
                print("3. Test the endpoint with: just test-runpod")
    else:
        print(f"Unknown command: {command}")
        sys.exit(1)


if __name__ == "__main__":
    main()
