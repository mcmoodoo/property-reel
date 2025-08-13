# RunPod container with BLIP-2 for frame analysis
FROM pytorch/pytorch:2.1.0-cuda12.1-cudnn8-runtime

# Set environment variables
ENV DEBIAN_FRONTEND=noninteractive
ENV PYTHONUNBUFFERED=1
ENV PIP_NO_CACHE_DIR=1

# Install system dependencies
RUN apt-get update && apt-get install -y --no-install-recommends \
    python3-pip \
    python3-opencv \
    ffmpeg \
    libsm6 \
    libxext6 \
    libxrender1 \
    libgomp1 \
    libglib2.0-0 \
    wget \
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