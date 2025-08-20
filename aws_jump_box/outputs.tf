output "instance_id" {
  description = "ID of the EC2 instance"
  value       = aws_instance.jump_box.id
}

output "public_ip" {
  description = "Elastic IP address of the jump box"
  value       = aws_eip.jump_box_eip.public_ip
}

output "ssh_connection_command" {
  description = "SSH command to connect to the jump box"
  value       = "ssh -i ~/.ssh/id_ed25519 ubuntu@${aws_eip.jump_box_eip.public_ip}"
}

output "security_group_id" {
  description = "ID of the security group"
  value       = aws_security_group.jump_box_sg.id
}

output "ami_id" {
  description = "AMI ID used for the instance"
  value       = aws_instance.jump_box.ami
}

output "availability_zone" {
  description = "Availability zone of the instance"
  value       = aws_instance.jump_box.availability_zone
}