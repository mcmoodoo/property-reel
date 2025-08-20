# AWS Jump Box

Terraform configuration for an Ubuntu EC2 jump box with Podman/Docker for building and pushing container images.

## Features

- Latest Ubuntu 24.04 LTS AMI
- Elastic IP for persistent public access
- Security group allowing SSH from anywhere (0.0.0.0/0)
- Pre-installed tools: Podman, Buildah, Skopeo, Just, AWS CLI v2, GitHub CLI
- SSH key from `~/.ssh/id_ed25519.pub`

## Usage

1. Initialize Terraform:
```bash
terraform init
```

2. Review the plan:
```bash
terraform plan
```

3. Deploy:
```bash
terraform apply
```

4. Connect to the jump box:
```bash
# Use the output command
terraform output ssh_connection_command

# Or manually
ssh -i ~/.ssh/id_ed25519 ubuntu@<elastic-ip>
```

5. Destroy when done:
```bash
terraform destroy
```

## Configuration

Edit `variables.tf` to customize:
- `aws_region`: AWS region (default: us-east-1)
- `instance_type`: EC2 instance type (default: t3.micro)
- `root_volume_size`: Root volume size in GB (default: 20)
- `instance_name`: Name for resources (default: jump-box)

## Security Note

The security group allows SSH from anywhere (0.0.0.0/0). For production use, restrict to specific IP ranges.