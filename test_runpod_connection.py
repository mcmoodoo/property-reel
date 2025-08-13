#!/usr/bin/env python3
"""Test RunPod connection and configuration."""

import asyncio
import os

from services.runpod_service import runpod_service


async def main():
    print("🔍 Testing RunPod Connection")
    print("=" * 50)

    # Check environment variables
    api_key = os.getenv("RUNPOD_API_KEY")
    endpoint_id = os.getenv("RUNPOD_ENDPOINT_ID")

    print(f"✓ API Key configured: {'Yes' if api_key else 'No'}")
    print(f"✓ Endpoint ID configured: {'Yes' if endpoint_id else 'No'}")

    if api_key:
        print(f"  API Key length: {len(api_key)} chars")
        print(f"  API Key prefix: {api_key[:10]}...")

    if endpoint_id:
        print(f"  Endpoint ID: {endpoint_id}")

    # Test connection
    print("\n📡 Testing API connection...")
    config = runpod_service.validate_configuration()
    for key, value in config.items():
        status = "✅" if value else "❌"
        print(f"  {status} {key}: {value}")

    # Try to submit a test job if configured
    if api_key and endpoint_id:
        print("\n🚀 Testing job submission...")
        try:
            # Create a minimal test payload
            test_urls = ["https://example.com/test.mp4"]
            test_property = {"property_type": "test"}
            test_job_id = "test-connection-123"

            result = await runpod_service.submit_job(
                video_s3_urls=test_urls, property_data=test_property, job_id=test_job_id
            )
            print(f"  ✅ Job submitted successfully: {result}")
        except Exception as e:
            print(f"  ❌ Job submission failed: {str(e)}")
            import traceback

            traceback.print_exc()


if __name__ == "__main__":
    asyncio.run(main())
