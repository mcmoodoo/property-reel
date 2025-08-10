# Multi-stage build for optimized RunPod ML inference container
# Stage 1: Builder - Install dependencies and download models
FROM pytorch/pytorch:2.6.0-cuda12.4-cudnn9-devel AS builder

# Set build-time environment
ENV DEBIAN_FRONTEND=noninteractive
ENV PIP_NO_CACHE_DIR=1
ENV PIP_DISABLE_PIP_VERSION_CHECK=1

# Install build dependencies in single layer
RUN apt-get update && apt-get install -y --no-install-recommends \
    build-essential \
    git \
    wget \
    && rm -rf /var/lib/apt/lists/* /tmp/* /var/tmp/*

# Create app directory
WORKDIR /app

# Copy and install Python dependencies first (for better caching)
COPY requirements-runpod.txt .

# Install Python packages in specific order for compatibility
RUN pip install --upgrade pip setuptools wheel && \
    pip install torch==2.6.0 torchvision==0.21.0 torchaudio==2.6.0 \
        --index-url https://download.pytorch.org/whl/cu124 && \
    pip install numpy==1.26.4 && \
    pip install -r requirements-runpod.txt

# Pre-download CLIP models to avoid cold start delays
RUN python -c "\
import os; \
os.environ['TRANSFORMERS_CACHE'] = '/models'; \
from transformers import CLIPModel, CLIPProcessor; \
model = CLIPModel.from_pretrained('openai/clip-vit-base-patch32', cache_dir='/models'); \
processor = CLIPProcessor.from_pretrained('openai/clip-vit-base-patch32', cache_dir='/models'); \
print('✅ Models cached successfully')"

# Stage 2: Runtime - Minimal production image
FROM pytorch/pytorch:2.6.0-cuda12.4-cudnn9-runtime AS runtime

# Set production environment
ENV DEBIAN_FRONTEND=noninteractive
ENV PYTHONUNBUFFERED=1
ENV PYTHONDONTWRITEBYTECODE=1
ENV PIP_NO_CACHE_DIR=1
ENV TRANSFORMERS_CACHE=/models
ENV HF_HOME=/models
ENV TORCH_CUDA_ARCH_LIST="7.5;8.0;8.6;8.9;9.0"
ENV CUDA_VISIBLE_DEVICES=0

# Create non-root user for security
RUN groupadd -r runpod && useradd -r -g runpod runpod

# Install minimal runtime dependencies
RUN apt-get update && apt-get install -y --no-install-recommends \
    ffmpeg \
    libsm6 \
    libxext6 \
    libxrender1 \
    libgomp1 \
    libglib2.0-0 \
    ca-certificates \
    && apt-get clean \
    && rm -rf /var/lib/apt/lists/* /tmp/* /var/tmp/* \
    && apt-get autoremove -y

# Set working directory
WORKDIR /app

# Copy Python packages from builder
COPY --from=builder /opt/conda /opt/conda

# Copy cached models from builder
COPY --from=builder /models /models

# Copy application code
COPY handler.py .

# Create temp directory and set permissions
RUN mkdir -p /tmp /app/logs && \
    chown -R runpod:runpod /app /tmp /models && \
    chmod +x handler.py

# Switch to non-root user
USER runpod

# Health check with timeout
HEALTHCHECK --interval=30s --timeout=10s --start-period=60s --retries=3 \
    CMD python -c "import torch, transformers; print(f'PyTorch: {torch.__version__}, CUDA: {torch.cuda.is_available()}')" || exit 1

# Labels for metadata
LABEL maintainer="Real Estate Video Pipeline" \
      version="1.0" \
      description="Optimized RunPod ML inference container for real estate video processing"

# Run the handler
CMD ["python", "-u", "handler.py"]