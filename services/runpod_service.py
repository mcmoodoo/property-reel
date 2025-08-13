"""RunPod service for managing serverless ML processing jobs."""

import logging

import requests

from utils.config import settings

logger = logging.getLogger(__name__)


class RunPodService:
    """Handle all RunPod serverless interactions - NO ML models here."""

    def __init__(self, api_key: str | None = None):
        """Initialize RunPod service."""
        self.api_key = api_key or settings.runpod_api_key
        self.base_url = "https://rest.runpod.io/v1"
        self.endpoint_id = settings.runpod_endpoint_id

        if not self.api_key:
            logger.warning("RunPod API key not configured")
        if not self.endpoint_id:
            logger.warning("RunPod endpoint ID not configured")

    async def submit_job(
        self, video_s3_urls: list[str], property_data: dict, job_id: str
    ) -> str:
        """Submit processing job to RunPod serverless function."""

        if not self.api_key or not self.endpoint_id:
            logger.error(f"Missing config - API key: {bool(self.api_key)}, Endpoint: {self.endpoint_id}")
            raise ValueError("RunPod API key and endpoint ID must be configured")

        # Prepare payload for RunPod ML processing
        payload = {
            "input": {
                "video_urls": video_s3_urls,
                "property_data": property_data,
                "job_id": job_id,
                "webhook_url": f"{settings.webhook_base_url}/runpod/{job_id}",
            }
        }

        headers = {
            "Authorization": f"Bearer {self.api_key}",
            "Content-Type": "application/json",
        }

        try:
            logger.info(
                f"Submitting job {job_id} to RunPod endpoint {self.endpoint_id} with {len(video_s3_urls)} videos"
            )
            logger.debug(f"Payload: {payload}")

            url = f"{self.base_url}/endpoints/{self.endpoint_id}/run"
            logger.info(f"POST to: {url}")
            
            response = requests.post(
                url,
                json=payload,
                headers=headers,
                timeout=30,
            )

            logger.info(f"Response status: {response.status_code}")
            if response.status_code != 200:
                logger.error(f"Response body: {response.text}")
            
            response.raise_for_status()

            result = response.json()
            runpod_job_id = result.get("id")

            if not runpod_job_id:
                logger.error(f"Response missing job ID: {result}")
                raise ValueError("RunPod did not return a job ID")

            logger.info(f"RunPod job submitted successfully: {runpod_job_id}")
            return runpod_job_id

        except requests.RequestException as e:
            logger.error(f"RunPod API request failed: {str(e)}")
            if hasattr(e, 'response') and e.response is not None:
                logger.error(f"Response status: {e.response.status_code}")
                logger.error(f"Response body: {e.response.text}")
            raise Exception(f"Failed to submit RunPod job: {str(e)}")
        except Exception as e:
            logger.error(f"RunPod job submission error: {str(e)}")
            raise

    async def get_job_status(self, runpod_job_id: str) -> dict:
        """Check RunPod job status."""

        if not self.api_key or not self.endpoint_id:
            raise ValueError("RunPod API key and endpoint ID must be configured")

        headers = {
            "Authorization": f"Bearer {self.api_key}",
            "Content-Type": "application/json",
        }

        try:
            response = requests.get(
                f"{self.base_url}/endpoints/{self.endpoint_id}/requests/{runpod_job_id}",
                headers=headers,
                timeout=10,
            )

            response.raise_for_status()
            return response.json()

        except requests.RequestException as e:
            logger.error(f"Failed to get RunPod job status: {str(e)}")
            return {"status": "UNKNOWN", "error": str(e)}

    async def cancel_job(self, runpod_job_id: str) -> bool:
        """Cancel RunPod job."""

        if not self.api_key or not self.endpoint_id:
            raise ValueError("RunPod API key and endpoint ID must be configured")

        headers = {
            "Authorization": f"Bearer {self.api_key}",
            "Content-Type": "application/json",
        }

        try:
            response = requests.post(
                f"{self.base_url}/endpoints/{self.endpoint_id}/requests/{runpod_job_id}/cancel",
                headers=headers,
                timeout=10,
            )

            response.raise_for_status()
            logger.info(f"RunPod job {runpod_job_id} cancelled successfully")
            return True

        except requests.RequestException as e:
            logger.error(f"Failed to cancel RunPod job: {str(e)}")
            return False

    def validate_configuration(self) -> dict[str, bool]:
        """Validate RunPod service configuration."""

        return {
            "api_key_configured": bool(self.api_key),
            "endpoint_id_configured": bool(self.endpoint_id),
            "base_url_reachable": self._test_connection(),
        }

    def _test_connection(self) -> bool:
        """Test connection to RunPod API."""

        if not self.api_key:
            return False

        try:
            headers = {
                "Authorization": f"Bearer {self.api_key}",
                "Content-Type": "application/json",
            }

            # Test with a simple API call (list endpoints)
            response = requests.get(
                f"{self.base_url}/endpoints", headers=headers, timeout=5
            )

            return response.status_code == 200

        except requests.RequestException:
            return False


# Global service instance
runpod_service = RunPodService()
