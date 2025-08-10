# Lightweight POC container for video stitching
FROM python:3.10-slim

# Set environment variables
ENV DEBIAN_FRONTEND=noninteractive
ENV PYTHONUNBUFFERED=1
ENV PIP_NO_CACHE_DIR=1

# Install system dependencies
RUN apt-get update && apt-get install -y --no-install-recommends \
    ffmpeg \
    libsm6 \
    libxext6 \
    libxrender1 \
    libgomp1 \
    libglib2.0-0 \
    && apt-get clean \
    && rm -rf /var/lib/apt/lists/*

# Set working directory
WORKDIR /app

# Copy requirements and install Python dependencies
COPY requirements-runpod.txt .
RUN pip install --upgrade pip && \
    pip install -r requirements-runpod.txt

# Copy handler
COPY handler.py .

# Create temp directory
RUN mkdir -p /tmp

# Health check
HEALTHCHECK --interval=30s --timeout=10s --start-period=30s --retries=3 \
    CMD python -c "import cv2, boto3; print('✅ Dependencies loaded')" || exit 1

# Run the handler
CMD ["python", "-u", "handler.py"]