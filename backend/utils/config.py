"""Configuration management for the real estate pipeline backend."""

import os
from typing import List
from pydantic_settings import BaseSettings
from pydantic import Field


class Settings(BaseSettings):
    """Application settings loaded from environment variables."""

    # Database
    database_url: str = Field(default="sqlite:///./real_estate.db")
    redis_url: str = Field(default="redis://localhost:6379/0")

    # AWS S3
    aws_access_key_id: str = Field(default="")
    aws_secret_access_key: str = Field(default="")
    aws_region: str = Field(default="us-east-1")
    s3_bucket_videos: str = Field(default="real-estate-videos")
    s3_bucket_results: str = Field(default="real-estate-results")

    # RunPod
    runpod_api_key: str = Field(default="")
    runpod_endpoint_id: str = Field(default="")

    # API Configuration
    api_host: str = Field(default="0.0.0.0")
    api_port: int = Field(default=8000)
    debug: bool = Field(default=False)

    # Security
    secret_key: str = Field(default="dev-secret-key-change-in-production")
    cors_origins: str = Field(default="http://localhost:3000")

    # Webhook
    webhook_base_url: str = Field(default="http://localhost:8000/webhook")

    @property
    def cors_origins_list(self) -> List[str]:
        """Convert CORS origins string to list."""
        return [origin.strip() for origin in self.cors_origins.split(",")]

    class Config:
        env_file = ".env"
        case_sensitive = False


# Global settings instance
settings = Settings()
