output "api_url" {
  description = "Public URL of the Omni-One API (health + Seller OS)."
  value       = "http://${aws_instance.omni_one.public_ip}:${var.app_port}"
}

output "health_url" {
  description = "Liveness endpoint (also the Docker/k8s healthcheck path)."
  value       = "http://${aws_instance.omni_one.public_ip}:${var.app_port}/health"
}

output "instance_id" {
  description = "EC2 instance id of the single-box."
  value       = aws_instance.omni_one.id
}
