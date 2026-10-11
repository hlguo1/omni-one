variable "region" {
  description = "AWS region for the single-box deploy."
  type        = string
  default     = "us-east-1"
}

variable "instance_type" {
  description = "EC2 size. t3.small is enough for Seller OS demo load."
  type        = string
  default     = "t3.small"
}

variable "app_port" {
  description = "Host/container port the API listens on ($PORT)."
  type        = number
  default     = 5003
}

variable "data_volume_size_gb" {
  description = "EBS volume size for ./data (DuckDB + audit + closes)."
  type        = number
  default     = 20
}

variable "app_version" {
  description = "omni-one image tag (must match Chart/app version)."
  type        = string
  default     = "1.1.0"
}

variable "key_name" {
  description = "Existing EC2 key pair for SSH (empty = no SSH ingress)."
  type        = string
  default     = ""
}

variable "allowed_http_cidr" {
  description = "CIDR allowed to reach the API port. Narrow this in prod."
  type        = string
  default     = "0.0.0.0/0"
}
