variable "aws_region" {
  description = "AWS region for the jump box"
  type        = string
  default     = "us-east-1"
}

variable "instance_name" {
  description = "Name for the jump box instance and related resources"
  type        = string
  default     = "jump-box"
}

variable "instance_type" {
  description = "EC2 instance type"
  type        = string
  default     = "t3.2xlarge"
}

variable "root_volume_size" {
  description = "Root volume size in GB"
  type        = number
  default     = 50
}

variable "ssh_public_key_path" {
  description = "Path to SSH public key file"
  type        = string
  default     = "/home/mcmoodoo/.ssh/id_ed25519.pub"
}

