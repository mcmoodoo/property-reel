terraform {
  required_version = ">= 1.0"
  required_providers {
    aws = {
      source  = "hashicorp/aws"
      version = "~> 5.0"
    }
  }
}

provider "aws" {
  region = var.aws_region
}

# Data source to get the latest Ubuntu 24.04 LTS AMI
data "aws_ami" "ubuntu" {
  most_recent = true
  owners      = ["099720109477"] # Canonical

  filter {
    name   = "name"
    values = ["ubuntu/images/hvm-ssd-gp3/ubuntu-noble-24.04-amd64-server-*"]
  }

  filter {
    name   = "virtualization-type"
    values = ["hvm"]
  }
}

# SSH Key Pair
resource "aws_key_pair" "jump_box_key" {
  key_name   = "${var.instance_name}-key"
  public_key = file(var.ssh_public_key_path)

  tags = {
    Name = "${var.instance_name}-key"
  }
}

# Security Group for SSH access
resource "aws_security_group" "jump_box_sg" {
  name        = "${var.instance_name}-sg"
  description = "Security group for jump box with SSH access"

  # SSH from anywhere
  ingress {
    description = "SSH from anywhere"
    from_port   = 22
    to_port     = 22
    protocol    = "tcp"
    cidr_blocks = ["0.0.0.0/0"]
  }

  # Allow all outbound traffic
  egress {
    description = "All outbound traffic"
    from_port   = 0
    to_port     = 0
    protocol    = "-1"
    cidr_blocks = ["0.0.0.0/0"]
  }

  tags = {
    Name = "${var.instance_name}-sg"
  }
}

# EC2 Instance
resource "aws_instance" "jump_box" {
  ami           = data.aws_ami.ubuntu.id
  instance_type = var.instance_type

  key_name               = aws_key_pair.jump_box_key.key_name
  vpc_security_group_ids = [aws_security_group.jump_box_sg.id]

  root_block_device {
    volume_size = var.root_volume_size
    volume_type = "gp3"
    encrypted   = true
  }

  user_data = templatefile("${path.module}/user_data.sh", {
    instance_name = var.instance_name
  })

  tags = {
    Name = var.instance_name
  }
}

# Elastic IP
resource "aws_eip" "jump_box_eip" {
  domain = "vpc"

  tags = {
    Name = "${var.instance_name}-eip"
  }
}

# Associate Elastic IP with the instance
resource "aws_eip_association" "jump_box_eip_assoc" {
  instance_id   = aws_instance.jump_box.id
  allocation_id = aws_eip.jump_box_eip.id
}