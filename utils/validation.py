"""Input validation utilities."""

import mimetypes

from fastapi import UploadFile
from pydantic import BaseModel, Field, validator


class PropertyData(BaseModel):
    """Property metadata validation model."""

    property_type: str = Field(default="residential", description="Type of property")
    bedrooms: int | None = Field(
        default=None, ge=0, le=20, description="Number of bedrooms"
    )
    bathrooms: float | None = Field(
        default=None, ge=0, le=20, description="Number of bathrooms"
    )
    square_feet: int | None = Field(
        default=None, ge=100, le=50000, description="Square footage"
    )
    price: int | None = Field(default=None, ge=0, description="Property price")
    address: str | None = Field(
        default=None, max_length=500, description="Property address"
    )
    description: str | None = Field(
        default=None, max_length=2000, description="Property description"
    )

    @validator("property_type")
    def validate_property_type(cls, v):
        valid_types = [
            "residential",
            "commercial",
            "condo",
            "townhouse",
            "apartment",
            "land",
        ]
        if v.lower() not in valid_types:
            raise ValueError(f"Property type must be one of: {valid_types}")
        return v.lower()


class JobResponse(BaseModel):
    """Response model for job creation."""

    job_id: str
    status: str
    video_count: int
    estimated_completion: str


class JobStatus(BaseModel):
    """Job status response model."""

    job_id: str
    status: str
    progress: int = Field(ge=0, le=100)
    result_url: str | None = None
    error_message: str | None = None
    created_at: str | None = None
    completed_at: str | None = None


def validate_video_files(files: list[UploadFile]) -> list[str]:
    """Validate uploaded video files."""

    errors = []

    # Check file count
    if len(files) == 0:
        errors.append("At least one video file is required")
    elif len(files) > 20:
        errors.append("Maximum 20 video files allowed")

    # Validate each file
    for i, file in enumerate(files):
        # Check file size (100MB limit per file)
        if hasattr(file, "size") and file.size > 100 * 1024 * 1024:
            errors.append(f"File {i + 1} ({file.filename}) exceeds 100MB limit")

        # Check file type
        mime_type, _ = mimetypes.guess_type(file.filename)
        if not mime_type or not mime_type.startswith("video/"):
            errors.append(f"File {i + 1} ({file.filename}) is not a valid video file")

        # Check file extension
        valid_extensions = [
            ".mp4",
            ".mov",
            ".avi",
            ".mkv",
            ".MP4",
            ".MOV",
            ".AVI",
            ".MKV",
        ]
        if not any(
            file.filename.lower().endswith(ext.lower()) for ext in valid_extensions
        ):
            errors.append(
                f"File {i + 1} ({file.filename}) has unsupported format. Allowed: {valid_extensions}"
            )

    return errors


def validate_job_id(job_id: str) -> bool:
    """Validate job ID format."""
    import uuid

    try:
        uuid.UUID(job_id)
        return True
    except ValueError:
        return False
