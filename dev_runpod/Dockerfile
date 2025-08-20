# Base: same as your Pod
FROM docker.io/runpod/pytorch:2.8.0-py3.11-cuda12.8.1-cudnn-devel-ubuntu22.04

# Keep noninteractive APT and slim layers
ENV DEBIAN_FRONTEND=noninteractive \
    PIP_NO_CACHE_DIR=1 \
    PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1

# OS deps (headless OpenCV + ffmpeg and common libs)
RUN apt-get update && apt-get install -y --no-install-recommends \
      python3-pip \
      ffmpeg \
      python3-opencv \
      libsm6 libxext6 libxrender1 libgomp1 libglib2.0-0 \
      wget ca-certificates \
    && rm -rf /var/lib/apt/lists/*

# Python tooling
RUN python3 -m pip install --upgrade pip setuptools wheel

# Python libs (UNPINNED latest — keep torch from base image as-is)
# Add a few helpful extras for HF
RUN pip install --upgrade \
      boto3 \
      opencv-python-headless \
      requests \
      numpy \
      Pillow \
      transformers \
      accelerate \
      sentencepiece \
      protobuf \
      scipy \
      timm \
      tokenizers \
      safetensors \
      huggingface-hub

# (Optional) place caches on the persistent volume
ENV HF_HOME=/workspace/.hf \
    TRANSFORMERS_CACHE=/workspace/.cache/huggingface \
    MPLCONFIGDIR=/workspace/.cache/matplotlib

WORKDIR /workspace
CMD ["/bin/bash"]
