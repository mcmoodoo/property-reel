#!/usr/bin/env python3
"""Test script for S3 result download functionality."""

import asyncio
import io
import logging
from services.s3_service import S3Service
from utils.config import settings

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)


async def test_result_download():
    """Test result file download from S3."""

    print("📥 Testing S3 Result Download Functionality")
    print("=" * 50)

    # Create a fresh S3 service instance
    s3_service = S3Service()

    if not s3_service.s3_client:
        print("❌ S3 client not initialized")
        return False

    job_id = "test-job-download-67890"

    try:
        # First, create some mock result files
        print(f"📤 Creating mock result files for job {job_id}...")

        # Upload mock result files to different categories
        mock_results = {
            "results/test-job-download-67890/clips/highlight_001.mp4": b"fake video clip data",
            "results/test-job-download-67890/clips/highlight_002.mp4": b"fake video clip data 2",
            "results/test-job-download-67890/thumbnails/thumb_001.jpg": b"fake thumbnail data",
            "results/test-job-download-67890/metadata/analysis.json": b'{"score": 0.95, "clips": 2}',
            "results/test-job-download-67890/metadata/report.txt": b"Processing completed successfully",
        }

        # Upload mock result files
        for s3_key, content in mock_results.items():
            s3_service.s3_client.put_object(
                Bucket=settings.s3_bucket_results,
                Key=s3_key,
                Body=content,
                ContentType="application/octet-stream",
            )

        print(f"✅ Created {len(mock_results)} mock result files")

        # Test result existence check
        print(f"\n🔍 Testing result existence check...")

        clips_exist = await s3_service.check_result_exists(job_id, "clips")
        print(f"✅ Clips exist: {clips_exist}")

        thumbnails_exist = await s3_service.check_result_exists(job_id, "thumbnails")
        print(f"✅ Thumbnails exist: {thumbnails_exist}")

        nonexistent_exist = await s3_service.check_result_exists(
            "nonexistent-job", "clips"
        )
        print(f"✅ Nonexistent job check (should be False): {nonexistent_exist}")

        # Test file listing
        print(f"\n📋 Testing result file listing...")

        result_files = await s3_service.list_result_files(job_id)
        print(f"✅ Found result files:")
        print(f"  Clips: {len(result_files['clips'])} files")
        for clip in result_files["clips"]:
            print(f"    - {clip}")

        print(f"  Thumbnails: {len(result_files['thumbnails'])} files")
        for thumb in result_files["thumbnails"]:
            print(f"    - {thumb}")

        print(f"  Metadata: {len(result_files['metadata'])} files")
        for meta in result_files["metadata"]:
            print(f"    - {meta}")

        # Test presigned URL generation for downloads
        print(f"\n🔗 Testing download URL generation...")

        if result_files["clips"]:
            clip_key = result_files["clips"][0]
            download_url = await s3_service.generate_presigned_url(
                clip_key,
                bucket=settings.s3_bucket_results,
                expiration=3600,  # 1 hour
            )
            print(f"✅ Clip download URL generated: {download_url[:80]}...")

        if result_files["metadata"]:
            meta_key = result_files["metadata"][0]
            meta_url = await s3_service.generate_presigned_url(
                meta_key, bucket=settings.s3_bucket_results, expiration=3600
            )
            print(f"✅ Metadata download URL generated: {meta_url[:80]}...")

        # Test bulk URL generation for all results
        print(f"\n🔗 Testing bulk download URL generation...")

        download_urls = {}

        # Generate URLs for all clips
        for clip_key in result_files["clips"]:
            download_urls[clip_key] = await s3_service.generate_presigned_url(
                clip_key,
                bucket=settings.s3_bucket_results,
                expiration=7200,  # 2 hours for results
            )

        # Generate URLs for all thumbnails
        for thumb_key in result_files["thumbnails"]:
            download_urls[thumb_key] = await s3_service.generate_presigned_url(
                thumb_key, bucket=settings.s3_bucket_results, expiration=7200
            )

        print(f"✅ Generated {len(download_urls)} download URLs")

        # Test URL format validation
        print(f"\n🔍 Validating URL formats...")

        for key, url in download_urls.items():
            if "https://" in url and "AWSAccessKeyId" in url and "Expires" in url:
                print(f"✅ Valid presigned URL format for {key.split('/')[-1]}")
            else:
                print(f"❌ Invalid URL format for {key}")

        # Cleanup test files
        print(f"\n🧹 Cleaning up test result files...")

        # Delete all test result files
        for s3_key in mock_results.keys():
            s3_service.s3_client.delete_object(
                Bucket=settings.s3_bucket_results, Key=s3_key
            )

        print("✅ Cleanup completed")

        return True

    except Exception as e:
        print(f"❌ Download test failed: {str(e)}")
        return False


if __name__ == "__main__":
    success = asyncio.run(test_result_download())
    if success:
        print("\n🎉 All S3 download tests passed!")
    else:
        print("\n💥 S3 download tests failed!")
