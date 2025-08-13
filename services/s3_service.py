"""S3 service for handling video uploads and results storage."""

import logging
import os
from typing import List

import boto3
from botocore.exceptions import ClientError, NoCredentialsError
from fastapi import UploadFile

from utils.config import settings

logger = logging.getLogger(__name__)


class S3Service:
    """Handle all S3 operations for video and results storage."""

    def __init__(self):
        """Initialize S3 client."""
        try:
            # Try explicit credentials first, then fall back to AWS credential chain
            if (
                settings.aws_video_api_access_key_id
                and settings.aws_video_api_secret_access_key
            ):
                self.s3_client = boto3.client(
                    "s3",
                    aws_access_key_id=settings.aws_video_api_access_key_id,
                    aws_secret_access_key=settings.aws_video_api_secret_access_key,
                    region_name=settings.aws_region,
                )
                logger.info("Using S3 credentials from environment variables")
            else:
                # Use AWS credential chain (CLI, IAM roles, etc.)
                self.s3_client = boto3.client("s3", region_name=settings.aws_region)
                logger.info("Using S3 credentials from AWS credential chain")

            self.video_bucket = settings.s3_bucket_videos
            self.results_bucket = settings.s3_bucket_results

        except NoCredentialsError:
            logger.warning("AWS credentials not configured")
            self.s3_client = None
        except Exception as e:
            logger.error(f"Failed to initialize S3 client: {e}")
            self.s3_client = None

    def validate_file(self, file: UploadFile) -> tuple[bool, str]:
        """Validate uploaded file for video processing."""

        # Check file size (max 500MB)
        max_size = 500 * 1024 * 1024  # 500MB in bytes
        if hasattr(file, "size") and file.size and file.size > max_size:
            return (
                False,
                f"File size {file.size / 1024 / 1024:.1f}MB exceeds maximum {max_size / 1024 / 1024}MB",
            )

        # Check file extension
        allowed_extensions = {".mp4", ".avi", ".mov", ".mkv", ".m4v", ".webm", ".flv"}
        file_extension = os.path.splitext(file.filename)[1].lower()

        if file_extension not in allowed_extensions:
            return (
                False,
                f"File type '{file_extension}' not supported. Allowed: {', '.join(allowed_extensions)}",
            )

        # Check content type
        allowed_content_types = {
            "video/mp4",
            "video/avi",
            "video/quicktime",
            "video/x-msvideo",
            "video/x-matroska",
            "video/webm",
            "video/x-flv",
        }

        if file.content_type and file.content_type not in allowed_content_types:
            logger.warning(
                f"Unexpected content type: {file.content_type} for {file.filename}"
            )

        # Check filename
        if not file.filename or len(file.filename) > 255:
            return False, "Invalid filename"

        return True, "File validation passed"

    async def upload_video_file(
        self, file: UploadFile, job_id: str, file_index: int
    ) -> str:
        """Upload video file to S3 and return URL."""

        if not self.s3_client:
            raise ValueError("S3 client not configured")

        # Validate file before upload
        is_valid, validation_message = self.validate_file(file)
        if not is_valid:
            raise ValueError(f"File validation failed: {validation_message}")

        # Generate unique filename
        file_extension = os.path.splitext(file.filename)[1]
        s3_key = f"uploads/{job_id}/video_{file_index:03d}{file_extension}"

        try:
            # Reset file pointer to beginning
            await file.seek(0)

            # Upload file
            self.s3_client.upload_fileobj(
                file.file,
                self.video_bucket,
                s3_key,
                ExtraArgs={
                    "ContentType": file.content_type or "video/mp4",
                    "Metadata": {
                        "original_filename": file.filename,
                        "job_id": job_id,
                        "file_index": str(file_index),
                    },
                },
            )

            # Generate S3 URL
            s3_url = f"s3://{self.video_bucket}/{s3_key}"

            logger.info(f"Uploaded video file {file.filename} to {s3_url}")
            return s3_url

        except ClientError as e:
            error_code = e.response.get("Error", {}).get("Code", "Unknown")
            error_message = e.response.get("Error", {}).get("Message", str(e))

            if error_code == "NoSuchBucket":
                logger.error(f"Bucket {self.video_bucket} does not exist")
                raise Exception(f"Upload bucket not found: {self.video_bucket}")
            elif error_code == "AccessDenied":
                logger.error(f"Access denied to bucket {self.video_bucket}")
                raise Exception("Insufficient permissions for video upload")
            elif error_code == "InvalidRequest":
                logger.error(f"Invalid upload request: {error_message}")
                raise Exception(f"Invalid upload request: {error_message}")
            else:
                logger.error(f"S3 upload failed [{error_code}]: {error_message}")
                raise Exception(f"S3 upload failed: {error_message}")
        except Exception as e:
            logger.error(f"Video upload error: {str(e)}")
            raise Exception(f"Upload failed: {str(e)}")

    async def upload_multiple_videos(
        self, files: list[UploadFile], job_id: str
    ) -> list[str]:
        """Upload multiple video files to S3."""

        s3_urls = []

        for i, file in enumerate(files):
            try:
                s3_url = await self.upload_video_file(file, job_id, i)
                s3_urls.append(s3_url)

            except Exception as e:
                logger.error(f"Failed to upload file {file.filename}: {str(e)}")
                # Clean up already uploaded files
                await self._cleanup_job_uploads(job_id)
                raise Exception(f"Upload failed for {file.filename}: {str(e)}")

        logger.info(f"Successfully uploaded {len(s3_urls)} videos for job {job_id}")
        return s3_urls

    async def generate_presigned_url(
        self, s3_key: str, bucket: str | None = None, expiration: int = 3600
    ) -> str:
        """Generate presigned URL for file access."""

        if not self.s3_client:
            raise ValueError("S3 client not configured")

        bucket = bucket or self.results_bucket

        try:
            url = self.s3_client.generate_presigned_url(
                "get_object",
                Params={"Bucket": bucket, "Key": s3_key},
                ExpiresIn=expiration,
            )
            return url

        except ClientError as e:
            logger.error(f"Failed to generate presigned URL: {str(e)}")
            raise Exception(f"Failed to generate download URL: {str(e)}")

    async def check_result_exists(
        self, job_id: str, result_type: str = "clips"
    ) -> bool:
        """Check if processing results exist in S3."""

        if not self.s3_client:
            return False

        try:
            # Check for results directory
            result_prefix = f"results/{job_id}/{result_type}/"

            response = self.s3_client.list_objects_v2(
                Bucket=self.results_bucket, Prefix=result_prefix, MaxKeys=1
            )

            return "Contents" in response and len(response["Contents"]) > 0

        except ClientError:
            return False

    async def list_result_files(self, job_id: str) -> dict[str, list[str]]:
        """List all result files for a job."""

        if not self.s3_client:
            raise ValueError("S3 client not configured")

        result_files = {"clips": [], "thumbnails": [], "metadata": []}

        try:
            # List all files in the job's results directory
            response = self.s3_client.list_objects_v2(
                Bucket=self.results_bucket, Prefix=f"results/{job_id}/"
            )

            if "Contents" in response:
                for obj in response["Contents"]:
                    key = obj["Key"]

                    if "clips/" in key and key.endswith(".mp4"):
                        result_files["clips"].append(key)
                    elif "thumbnails/" in key and key.endswith((".jpg", ".png")):
                        result_files["thumbnails"].append(key)
                    elif key.endswith((".json", ".txt")):
                        result_files["metadata"].append(key)

            return result_files

        except ClientError as e:
            logger.error(f"Failed to list result files: {str(e)}")
            raise Exception(f"Failed to list results: {str(e)}")

    async def _cleanup_job_uploads(self, job_id: str) -> None:
        """Clean up uploaded files for a failed job."""

        if not self.s3_client:
            return

        try:
            # List all files for this job
            response = self.s3_client.list_objects_v2(
                Bucket=self.video_bucket, Prefix=f"uploads/{job_id}/"
            )

            if "Contents" in response:
                # Delete all files
                delete_keys = [{"Key": obj["Key"]} for obj in response["Contents"]]

                if delete_keys:
                    self.s3_client.delete_objects(
                        Bucket=self.video_bucket, Delete={"Objects": delete_keys}
                    )

                    logger.info(
                        f"Cleaned up {len(delete_keys)} uploaded files for job {job_id}"
                    )

        except ClientError as e:
            logger.warning(f"Failed to cleanup uploads for job {job_id}: {str(e)}")

    def validate_configuration(self) -> dict[str, bool]:
        """Validate S3 service configuration."""

        # Check if credentials are available (either env vars or AWS credential chain)
        credentials_available = bool(
            settings.aws_video_api_access_key_id
            and settings.aws_video_api_secret_access_key
        )
        if not credentials_available:
            # Test if AWS credential chain works
            try:
                boto3.Session().get_credentials()
                credentials_available = True
            except:
                pass

        config_status = {
            "credentials_configured": credentials_available,
            "buckets_configured": bool(
                settings.s3_bucket_videos and settings.s3_bucket_results
            ),
            "s3_client_initialized": self.s3_client is not None,
            "video_bucket_accessible": False,
            "results_bucket_accessible": False,
        }

        # Test bucket access
        if self.s3_client:
            config_status["video_bucket_accessible"] = self._test_bucket_access(
                self.video_bucket
            )
            config_status["results_bucket_accessible"] = self._test_bucket_access(
                self.results_bucket
            )

        return config_status

    def _test_bucket_access(self, bucket_name: str) -> bool:
        """Test if bucket is accessible."""

        if not self.s3_client:
            return False

        try:
            self.s3_client.head_bucket(Bucket=bucket_name)
            return True

        except ClientError:
            return False

    async def create_bucket_if_not_exists(self, bucket_name: str) -> bool:
        """Create S3 bucket if it doesn't exist."""

        if not self.s3_client:
            raise ValueError("S3 client not configured")

        try:
            # Check if bucket exists
            self.s3_client.head_bucket(Bucket=bucket_name)
            logger.info(f"Bucket {bucket_name} already exists")
            return True

        except ClientError as e:
            error_code = int(e.response["Error"]["Code"])

            if error_code == 404:
                # Bucket doesn't exist, create it
                try:
                    if settings.aws_region == "us-east-1":
                        # us-east-1 doesn't need LocationConstraint
                        self.s3_client.create_bucket(Bucket=bucket_name)
                    else:
                        self.s3_client.create_bucket(
                            Bucket=bucket_name,
                            CreateBucketConfiguration={
                                "LocationConstraint": settings.aws_region
                            },
                        )

                    # Enable versioning for better data protection
                    self.s3_client.put_bucket_versioning(
                        Bucket=bucket_name,
                        VersioningConfiguration={"Status": "Enabled"},
                    )

                    logger.info(f"✅ Created S3 bucket: {bucket_name}")
                    return True

                except ClientError as create_error:
                    logger.error(
                        f"Failed to create bucket {bucket_name}: {create_error}"
                    )
                    return False
            else:
                logger.error(f"Access denied to bucket {bucket_name}: {e}")
                return False

    async def setup_buckets(self) -> dict[str, bool]:
        """Create required S3 buckets if they don't exist."""

        results = {}

        if self.video_bucket:
            results[self.video_bucket] = await self.create_bucket_if_not_exists(
                self.video_bucket
            )

        if self.results_bucket:
            results[self.results_bucket] = await self.create_bucket_if_not_exists(
                self.results_bucket
            )

        return results


# Global service instance
s3_service = S3Service()
