#!/usr/bin/env python3
"""Test script for S3 service connectivity and configuration."""

import asyncio
import logging

# Reload the service to pick up new configuration
from utils.config import settings
from services.s3_service import S3Service

# Create a fresh instance with updated config
s3_service = S3Service()

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)


async def test_s3_configuration():
    """Test S3 service configuration and connectivity."""

    print("🔍 Testing S3 Service Configuration")
    print("=" * 50)

    # Test configuration
    config_status = s3_service.validate_configuration()

    print("Configuration Status:")
    for key, value in config_status.items():
        status = "✅" if value else "❌"
        print(f"  {status} {key.replace('_', ' ').title()}: {value}")

    print("\nSettings:")
    print(f"  AWS Region: {settings.aws_region}")
    print(f"  Video Bucket: {settings.s3_bucket_videos}")
    print(f"  Results Bucket: {settings.s3_bucket_results}")
    print(f"  Credentials Configured: {bool(settings.aws_access_key_id)}")

    if not s3_service.s3_client:
        print("\n❌ S3 client not initialized. Check your AWS credentials.")
        print("\nTo configure S3:")
        print("1. Copy .env.example to .env")
        print("2. Set AWS_ACCESS_KEY_ID and AWS_SECRET_ACCESS_KEY")
        print("3. Set S3_BUCKET_VIDEOS and S3_BUCKET_RESULTS")
        return False

    # Test bucket access
    if (
        config_status["video_bucket_accessible"]
        and config_status["results_bucket_accessible"]
    ):
        print("\n✅ All S3 buckets are accessible!")

        # Test listing (should be empty initially)
        try:
            result_files = await s3_service.list_result_files("test-job-id")
            print(f"\n📁 Test listing result files: {result_files}")

        except Exception as e:
            print(f"\n⚠️  Could not test file listing: {e}")

        return True
    else:
        print(f"\n❌ Bucket access failed")
        print(
            f"  Video bucket ({settings.s3_bucket_videos}): {config_status['video_bucket_accessible']}"
        )
        print(
            f"  Results bucket ({settings.s3_bucket_results}): {config_status['results_bucket_accessible']}"
        )
        return False


if __name__ == "__main__":
    asyncio.run(test_s3_configuration())
