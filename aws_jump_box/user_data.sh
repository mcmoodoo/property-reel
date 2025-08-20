#!/bin/bash
set -e

# Ensure non-interactive mode for all commands
export DEBIAN_FRONTEND=noninteractive
export NEEDRESTART_MODE=a

# Update and upgrade system
apt-get update -y
apt-get upgrade -y -o Dpkg::Options::="--force-confdef" -o Dpkg::Options::="--force-confold"

# Install essential packages
apt-get install -y \
    curl \
    wget \
    git \
    vim \
    htop \
    build-essential \
    software-properties-common \
    apt-transport-https \
    ca-certificates \
    gnupg \
    lsb-release \
    jq \
    unzip

# Install Just command runner via snap
snap install just --classic

# Install Podman
apt-get install -y podman buildah skopeo

# Configure Podman for rootless operation
loginctl enable-linger ubuntu
echo "ubuntu:100000:65536" >>/etc/subuid
echo "ubuntu:100000:65536" >>/etc/subgid

# Install AWS CLI v2
curl "https://awscli.amazonaws.com/awscli-exe-linux-x86_64.zip" -o "awscliv2.zip"
unzip awscliv2.zip
./aws/install
rm -rf awscliv2.zip aws/

# Install GitHub CLI
curl -fsSL https://cli.github.com/packages/githubcli-archive-keyring.gpg | dd of=/usr/share/keyrings/githubcli-archive-keyring.gpg
chmod go+r /usr/share/keyrings/githubcli-archive-keyring.gpg
echo "deb [arch=$(dpkg --print-architecture) signed-by=/usr/share/keyrings/githubcli-archive-keyring.gpg] https://cli.github.com/packages stable main" | tee /etc/apt/sources.list.d/github-cli.list >/dev/null
apt-get update
apt-get install -y gh

# Set hostname
hostnamectl set-hostname ${instance_name}

# Create a welcome message
cat >/etc/motd <<'EOF'
========================================
       AWS Jump Box - Ready
========================================
- Podman, Buildah, Skopeo installed
- Just command runner installed
- AWS CLI v2 installed
- GitHub CLI installed
- SSH access configured

To build and push container images:
  podman build -t image:tag .
  podman push image:tag

To use Just:
  just --list

========================================
EOF

# Log completion
echo "User data script completed at $(date)" >>/var/log/user-data.log
