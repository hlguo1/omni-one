# Omni-One "VPC-lite" single-box: 1 x EC2 + EBS data volume + SG(:5003) + logs.
# Cheapest path that still looks like prod. For multi-AZ / autoscaled, use the
# k8s manifests or Helm chart instead of growing this file.
provider "aws" {
  region = var.region
}

data "aws_ami" "al2023" {
  most_recent = true
  owners      = ["amazon"]
  filter {
    name   = "name"
    values = ["al2023-ami-*-x86_64"]
  }
}

data "aws_vpc" "default" {
  default = true
}

resource "aws_security_group" "omni_one" {
  name        = "omni-one-sg"
  description = "Omni-One Seller OS single-box"
  vpc_id      = data.aws_vpc.default.id

  ingress {
    description = "Omni-One API"
    from_port   = var.app_port
    to_port     = var.app_port
    protocol    = "tcp"
    cidr_blocks = [var.allowed_http_cidr]
  }

  egress {
    description = "HTTPS egress (image pulls, optional LLM)"
    from_port   = 443
    to_port     = 443
    protocol    = "tcp"
    cidr_blocks = ["0.0.0.0/0"]
  }

  tags = { Name = "omni-one-sg" }
}

resource "aws_cloudwatch_log_group" "omni_one" {
  name              = "/omni-one/api"
  retention_in_days = 30
  tags              = { Name = "omni-one-logs" }
}

resource "aws_instance" "omni_one" {
  ami                    = data.aws_ami.al2023.id
  instance_type          = var.instance_type
  key_name               = var.key_name != "" ? var.key_name : null
  vpc_security_group_ids = [aws_security_group.omni_one.id]

  # ./data lives on its own EBS volume (survives instance replace).
  user_data = <<-EOF
    #!/bin/bash
    set -euo pipefail
    dnf install -y docker awscli
    systemctl enable --now docker
    mkdir -p /srv/omni-one/data
    # attach/mount done by volume_attachment + fstab below (nvme name varies; try both)
    mkfs.ext4 -F /dev/sdf || true
    mount /dev/sdf /srv/omni-one/data || mount /dev/nvme1n1 /srv/omni-one/data || true
    grep -q omni-one /etc/fstab || echo "/dev/sdf /srv/omni-one/data ext4 defaults,nofail 0 2" >> /etc/fstab
    docker run -d --restart unless-stopped --name omni-one \
      -p ${var.app_port}:5003 \
      -v /srv/omni-one/data:/app/data \
      -e PORT=5003 -e SELLER_LLM=off -e DUCKDB_PATH=/app/data/omni.duckdb \
      --log-driver awslogs --log-opt awslogs-group=/omni-one/api --log-opt awslogs-region=${var.region} \
      omni-one:${var.app_version}
  EOF

  tags = { Name = "omni-one-single-box" }
}

resource "aws_ebs_volume" "omni_data" {
  availability_zone = aws_instance.omni_one.availability_zone
  size              = var.data_volume_size_gb
  type              = "gp3"
  tags              = { Name = "omni-one-data" }
}

resource "aws_volume_attachment" "omni_data" {
  device_name = "/dev/sdf"
  volume_id   = aws_ebs_volume.omni_data.id
  instance_id = aws_instance.omni_one.id
}
