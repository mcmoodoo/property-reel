"""S3 service for handling video uploads and results storage."""

import boto3
import logging
import hashlib
import os
from typing import List, Optional, Dict
from botocore.exceptions import ClientError, NoCredentialsError
from fastapi import UploadFile
from utils.config import settings

logger = logging.getLogger(__name__)


class S3Service:
    """Handle all S3 operations for video and results storage."""
    
    def __init__(self):
        """Initialize S3 client."""
        try:
            self.s3_client = boto3.client(
                's3',
                aws_access_key_id=settings.aws_access_key_id,
                aws_secret_access_key=settings.aws_secret_access_key,
                region_name=settings.aws_region
            )
            
            self.video_bucket = settings.s3_bucket_videos
            self.results_bucket = settings.s3_bucket_results
            
        except NoCredentialsError:
            logger.warning("AWS credentials not configured")
            self.s3_client = None
    
    async def upload_video_file(
        self, 
        file: UploadFile, 
        job_id: str, 
        file_index: int
    ) -> str:
        """Upload video file to S3 and return URL."""
        
        if not self.s3_client:
            raise ValueError("S3 client not configured")
        
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
                    'ContentType': file.content_type or 'video/mp4',
                    'Metadata': {
                        'original_filename': file.filename,
                        'job_id': job_id,
                        'file_index': str(file_index)
                    }
                }
            )
            
            # Generate S3 URL
            s3_url = f"s3://{self.video_bucket}/{s3_key}"
            
            logger.info(f"Uploaded video file {file.filename} to {s3_url}")
            return s3_url
            
        except ClientError as e:
            logger.error(f"Failed to upload video file: {str(e)}")
            raise Exception(f"S3 upload failed: {str(e)}")
        except Exception as e:
            logger.error(f"Video upload error: {str(e)}")
            raise
    
    async def upload_multiple_videos(
        self, 
        files: List[UploadFile], 
        job_id: str
    ) -> List[str]:
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
        self, 
        s3_key: str, 
        bucket: Optional[str] = None,
        expiration: int = 3600
    ) -> str:
        """Generate presigned URL for file access."""
        
        if not self.s3_client:
            raise ValueError("S3 client not configured")
        
        bucket = bucket or self.results_bucket
        
        try:
            url = self.s3_client.generate_presigned_url(
                'get_object',
                Params={'Bucket': bucket, 'Key': s3_key},
                ExpiresIn=expiration
            )
            return url
            
        except ClientError as e:
            logger.error(f"Failed to generate presigned URL: {str(e)}")
            raise Exception(f"Failed to generate download URL: {str(e)}")
    
    async def check_result_exists(self, job_id: str, result_type: str = "clips") -> bool:
        """Check if processing results exist in S3."""
        
        if not self.s3_client:
            return False
        
        try:
            # Check for results directory
            result_prefix = f"results/{job_id}/{result_type}/"
            
            response = self.s3_client.list_objects_v2(
                Bucket=self.results_bucket,
                Prefix=result_prefix,
                MaxKeys=1
            )
            
            return 'Contents' in response and len(response['Contents']) > 0
            
        except ClientError:
            return False
    
    async def list_result_files(self, job_id: str) -> Dict[str, List[str]]:
        """List all result files for a job."""
        
        if not self.s3_client:
            raise ValueError("S3 client not configured")
        
        result_files = {
            'clips': [],
            'thumbnails': [],
            'metadata': []
        }
        
        try:
            # List all files in the job's results directory
            response = self.s3_client.list_objects_v2(
                Bucket=self.results_bucket,
                Prefix=f"results/{job_id}/"
            )
            
            if 'Contents' in response:
                for obj in response['Contents']:
                    key = obj['Key']
                    
                    if 'clips/' in key and key.endswith('.mp4'):
                        result_files['clips'].append(key)
                    elif 'thumbnails/' in key and key.endswith(('.jpg', '.png')):
                        result_files['thumbnails'].append(key)
                    elif key.endswith(('.json', '.txt')):
                        result_files['metadata'].append(key)
            
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
                Bucket=self.video_bucket,
                Prefix=f"uploads/{job_id}/"
            )
            
            if 'Contents' in response:
                # Delete all files
                delete_keys = [{'Key': obj['Key']} for obj in response['Contents']]
                
                if delete_keys:
                    self.s3_client.delete_objects(
                        Bucket=self.video_bucket,
                        Delete={'Objects': delete_keys}
                    )
                    
                    logger.info(f"Cleaned up {len(delete_keys)} uploaded files for job {job_id}")
        
        except ClientError as e:
            logger.warning(f"Failed to cleanup uploads for job {job_id}: {str(e)}")
    
    def validate_configuration(self) -> Dict[str, bool]:
        """Validate S3 service configuration."""
        
        config_status = {
            "credentials_configured": bool(
                settings.aws_access_key_id and 
                settings.aws_secret_access_key
            ),
            "buckets_configured": bool(
                settings.s3_bucket_videos and 
                settings.s3_bucket_results
            ),
            "s3_client_initialized": self.s3_client is not None,
            "video_bucket_accessible": False,
            "results_bucket_accessible": False
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


# Global service instance
s3_service = S3Service()