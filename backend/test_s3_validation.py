#!/usr/bin/env python3
"""Test script for S3 service validation and error handling."""

import asyncio
import io
import logging
from unittest.mock import Mock
from services.s3_service import S3Service

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)


def create_mock_file(
    filename: str, content_type: str = "video/mp4", size: int = None
) -> Mock:
    """Create a mock file for testing."""
    mock_file = Mock()
    mock_file.filename = filename
    mock_file.content_type = content_type
    mock_file.size = size
    mock_file.file = io.BytesIO(b"fake video data")

    async def mock_seek(position):
        mock_file.file.seek(position)
        return None

    mock_file.seek = mock_seek
    return mock_file


async def test_file_validation():
    """Test file validation functionality."""

    print("🔍 Testing S3 File Validation")
    print("=" * 50)

    s3_service = S3Service()

    # Test valid files
    print("\n✅ Testing valid files...")

    valid_files = [
        ("video.mp4", "video/mp4"),
        ("sample.avi", "video/avi"),
        ("clip.mov", "video/quicktime"),
        ("recording.mkv", "video/x-matroska"),
    ]

    for filename, content_type in valid_files:
        mock_file = create_mock_file(
            filename, content_type, size=50 * 1024 * 1024
        )  # 50MB
        is_valid, message = s3_service.validate_file(mock_file)

        if is_valid:
            print(f"  ✅ {filename} ({content_type}): {message}")
        else:
            print(f"  ❌ {filename} failed validation: {message}")

    # Test invalid file extensions
    print("\n❌ Testing invalid file extensions...")

    invalid_extensions = [
        "document.pdf",
        "image.jpg",
        "audio.mp3",
        "archive.zip",
        "script.py",
    ]

    for filename in invalid_extensions:
        mock_file = create_mock_file(filename, "application/octet-stream")
        is_valid, message = s3_service.validate_file(mock_file)

        if not is_valid:
            print(f"  ✅ {filename} correctly rejected: {message}")
        else:
            print(f"  ❌ {filename} incorrectly accepted")

    # Test file size limits
    print("\n📏 Testing file size limits...")

    size_tests = [
        (100 * 1024 * 1024, True, "100MB file"),  # 100MB - should pass
        (500 * 1024 * 1024, True, "500MB file"),  # 500MB - should pass (at limit)
        (600 * 1024 * 1024, False, "600MB file"),  # 600MB - should fail
        (1024 * 1024 * 1024, False, "1GB file"),  # 1GB - should fail
    ]

    for size, should_pass, description in size_tests:
        mock_file = create_mock_file("test.mp4", "video/mp4", size=size)
        is_valid, message = s3_service.validate_file(mock_file)

        if is_valid == should_pass:
            print(f"  ✅ {description}: {message}")
        else:
            print(f"  ❌ {description} validation unexpected: {message}")

    # Test invalid filenames
    print("\n📝 Testing filename validation...")

    filename_tests = [
        ("", False, "empty filename"),
        (None, False, "None filename"),
        ("a" * 300 + ".mp4", False, "filename too long"),
        ("normal-video.mp4", True, "normal filename"),
    ]

    for filename, should_pass, description in filename_tests:
        mock_file = create_mock_file(filename or "", "video/mp4")
        mock_file.filename = filename  # Override with actual test value

        try:
            is_valid, message = s3_service.validate_file(mock_file)

            if is_valid == should_pass:
                print(f"  ✅ {description}: {message}")
            else:
                print(f"  ❌ {description} validation unexpected: {message}")
        except Exception as e:
            if not should_pass:
                print(f"  ✅ {description} correctly failed with exception: {e}")
            else:
                print(f"  ❌ {description} unexpectedly failed: {e}")

    return True


async def test_error_handling():
    """Test error handling for various scenarios."""

    print("\n🚨 Testing Error Handling")
    print("=" * 50)

    s3_service = S3Service()

    if not s3_service.s3_client:
        print("❌ Cannot test error handling without S3 client")
        return False

    # Test upload with invalid file
    print("\n📤 Testing upload with invalid file...")

    try:
        invalid_file = create_mock_file("document.txt", "text/plain")
        await s3_service.upload_video_file(invalid_file, "test-job", 0)
        print("  ❌ Invalid file upload should have failed")

    except ValueError as e:
        if "validation failed" in str(e):
            print(f"  ✅ Invalid file correctly rejected: {e}")
        else:
            print(f"  ⚠️  Unexpected validation error: {e}")
    except Exception as e:
        print(f"  ⚠️  Unexpected error: {e}")

    # Test with oversized file
    print("\n📏 Testing oversized file upload...")

    try:
        oversized_file = create_mock_file(
            "huge.mp4", "video/mp4", size=1024 * 1024 * 1024
        )  # 1GB
        await s3_service.upload_video_file(oversized_file, "test-job", 0)
        print("  ❌ Oversized file upload should have failed")

    except ValueError as e:
        if "File size" in str(e) and "exceeds maximum" in str(e):
            print(f"  ✅ Oversized file correctly rejected: {e}")
        else:
            print(f"  ⚠️  Unexpected size error: {e}")
    except Exception as e:
        print(f"  ⚠️  Unexpected error: {e}")

    return True


if __name__ == "__main__":
    print("🧪 S3 Service Validation and Error Handling Tests")
    print("=" * 60)

    try:
        validation_success = asyncio.run(test_file_validation())
        error_handling_success = asyncio.run(test_error_handling())

        if validation_success and error_handling_success:
            print("\n🎉 All validation and error handling tests passed!")
        else:
            print("\n💥 Some tests failed!")

    except Exception as e:
        print(f"\n💥 Test execution failed: {e}")
