#!/usr/bin/env python3
"""Test script for S3 video upload functionality."""

import asyncio
import io
import logging
from unittest.mock import Mock

from services.s3_service import S3Service
from utils.config import settings

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)


async def test_video_upload():
    """Test video file upload to S3."""

    print("🎬 Testing S3 Video Upload Functionality")
    print("=" * 50)

    # Create a fresh S3 service instance
    s3_service = S3Service()

    if not s3_service.s3_client:
        print("❌ S3 client not initialized")
        return False

    # Create a mock video file
    mock_video_content = b"fake video data for testing purposes"
    mock_file = Mock()
    mock_file.filename = "test_video.mp4"
    mock_file.content_type = "video/mp4"
    mock_file.size = len(mock_video_content)  # Add size attribute
    mock_file.file = io.BytesIO(mock_video_content)

    # Make seek async and return a coroutine
    async def mock_seek(position):
        mock_file.file.seek(position)
        return None

    mock_file.seek = mock_seek

    job_id = "test-job-12345"

    try:
        print(f"📤 Uploading test video to job {job_id}...")

        # Test single file upload
        s3_url = await s3_service.upload_video_file(mock_file, job_id, 0)
        print(f"✅ Upload successful: {s3_url}")

        # Verify the URL format
        expected_key = f"uploads/{job_id}/video_000.mp4"
        expected_url = f"s3://{settings.s3_bucket_videos}/{expected_key}"

        if s3_url == expected_url:
            print("✅ URL format is correct")
        else:
            print(f"⚠️  URL format mismatch. Expected: {expected_url}, Got: {s3_url}")

        # Test multiple file upload
        print(f"📤 Testing multiple file upload...")

        # Create separate mock files for multiple upload
        def create_mock_file(filename):
            file_mock = Mock()
            file_mock.filename = filename
            file_mock.content_type = "video/mp4"
            file_mock.size = len(mock_video_content)  # Add size attribute
            file_mock.file = io.BytesIO(mock_video_content)

            async def file_seek(position):
                file_mock.file.seek(position)
                return None

            file_mock.seek = file_seek
            return file_mock

        mock_files = [
            create_mock_file("test_video_1.mp4"),
            create_mock_file("test_video_2.mp4"),
        ]

        s3_urls = await s3_service.upload_multiple_videos(mock_files, job_id + "-multi")
        print(f"✅ Multiple upload successful: {len(s3_urls)} files uploaded")

        for i, url in enumerate(s3_urls):
            print(f"  File {i}: {url}")

        print(f"\n📋 Testing file listing...")

        # Test listing files (should be empty since we uploaded to different job)
        result_files = await s3_service.list_result_files("nonexistent-job")
        print(f"✅ File listing works: {result_files}")

        print(f"\n🔗 Testing presigned URL generation...")

        # Test presigned URL generation
        test_key = f"uploads/{job_id}/video_000.mp4"
        presigned_url = await s3_service.generate_presigned_url(
            test_key,
            bucket=settings.s3_bucket_videos,
            expiration=300,  # 5 minutes
        )

        print(f"✅ Presigned URL generated: {presigned_url[:100]}...")

        print(f"\n🧹 Cleaning up test files...")

        # Cleanup test uploads
        await s3_service._cleanup_job_uploads(job_id)
        await s3_service._cleanup_job_uploads(job_id + "-multi")
        print("✅ Cleanup completed")

        return True

    except Exception as e:
        print(f"❌ Upload test failed: {str(e)}")
        return False


if __name__ == "__main__":
    success = asyncio.run(test_video_upload())
    if success:
        print("\n🎉 All S3 upload tests passed!")
    else:
        print("\n💥 S3 upload tests failed!")
